"""
Harvard Murray Archive Scraper — Improved Version (Repository #18)
--------------------------------------------------------------------
The Murray Research Archive data lives on Harvard Dataverse at:
https://dataverse.harvard.edu/dataverse/mra

Harvard Dataverse has a FREE public API — no login required for public datasets.

API endpoints used:
  Search:  GET /api/search?q={query}&subtree=mra&type=dataset&per_page=100
  Dataset: GET /api/datasets/:persistentId/?persistentId={doi}
  Files:   GET /api/datasets/:persistentId/versions/:version/files
  Download: GET /api/access/datafile/{file_id}

Run this script directly:
    python3 scripts/harvard_dataverse_scraper.py
"""

import sys
import requests
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import (
    project_exists, insert_project, insert_file,
    insert_keyword, insert_person, insert_license,
    ROLE_AUTHOR, ROLE_UNKNOWN, STATUS_NO_DOWNLOAD_LINK,
    STATUS_LOGIN_REQUIRED, STATUS_SUCCESS
)
from pipeline.downloader import download_file

REPO_ID = 2
REPO_URL = "https://www.murray.harvard.edu"
DATAVERSE_URL = "https://dataverse.harvard.edu"
REPO_FOLDER = "harvard"
DATA_ROOT = Path(__file__).parent.parent / "data"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Search queries for Murray Archive
SEARCH_QUERIES = [
    "interview",
    "qualitative",
    "longitudinal",
    "oral history",
    "life study",
    "survey",
]

# File extensions to download (skip huge binary files)
SKIP_EXTENSIONS = {".sav", ".dta"}  # SPSS/Stata files can be very large


def api_get(url, params=None):
    """Make a GET request to Harvard Dataverse API."""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [API ERROR] {url}: {e}")
        return None


def search_datasets(query, subtree="mra", per_page=100):
    """Search for datasets in the Murray Archive (mra) dataverse."""
    datasets = []
    start = 0

    while True:
        params = {
            "q": query,
            "subtree": subtree,
            "type": "dataset",
            "per_page": per_page,
            "start": start,
        }
        data = api_get(f"{DATAVERSE_URL}/api/search", params=params)
        if not data:
            break

        items = data.get("data", {}).get("items", [])
        if not items:
            break

        datasets.extend(items)
        total = data.get("data", {}).get("total_count", 0)
        print(f"    Query '{query}': got {len(items)} (total: {total}, collected: {len(datasets)})")

        if len(datasets) >= total or len(items) < per_page:
            break

        start += per_page
        time.sleep(0.5)

    return datasets


def get_dataset_files(doi):
    """Get list of files for a dataset using its DOI."""
    url = f"{DATAVERSE_URL}/api/datasets/:persistentId/versions/:latest/files"
    params = {"persistentId": doi}
    data = api_get(url, params=params)
    if data and data.get("status") == "OK":
        return data.get("data", [])
    return []


def get_dataset_metadata(doi):
    """Get full metadata for a dataset."""
    url = f"{DATAVERSE_URL}/api/datasets/:persistentId/"
    params = {"persistentId": doi}
    data = api_get(url, params=params)
    if data and data.get("status") == "OK":
        return data.get("data", {})
    return {}


def extract_metadata(item, full_meta=None):
    """Extract clean metadata from a search result or full metadata."""
    title = item.get("name") or item.get("title") or "Untitled"
    description = item.get("description") or ""
    doi = item.get("global_id") or item.get("identifier") or None

    # Authors
    authors = []
    for author in (item.get("authors") or []):
        if isinstance(author, str) and author.strip():
            authors.append(author.strip())

    # Keywords
    keywords = []
    for kw in (item.get("keywords") or []):
        if isinstance(kw, str) and kw.strip():
            keywords.append(kw.strip())

    # Publication date
    pub_date = (
        item.get("published_at") or
        item.get("createdAt") or
        item.get("publication_date") or
        None
    )
    if pub_date and len(str(pub_date)) > 10:
        pub_date = str(pub_date)[:10]

    # License
    license_str = item.get("license") or "CC0"

    return {
        "title": str(title)[:500],
        "description": str(description)[:2000],
        "language": "en",
        "doi": str(doi) if doi else None,
        "upload_date": str(pub_date)[:20] if pub_date else None,
        "authors": authors,
        "keywords": keywords,
        "license": str(license_str)[:200],
    }


def main():
    print("=" * 50)
    print("  Harvard Murray Archive — Dataverse API Scraper")
    print("=" * 50)

    # Collect unique datasets across all queries
    seen_dois = {}

    for query in SEARCH_QUERIES:
        print(f"\n  Searching Murray Archive for: '{query}'")
        datasets = search_datasets(query, subtree="mra")
        for ds in datasets:
            doi = ds.get("global_id")
            if doi and doi not in seen_dois:
                seen_dois[doi] = ds
        time.sleep(1)

    print(f"\n  Found {len(seen_dois)} unique datasets in Murray Archive.")

    # Also try broader Harvard Dataverse search for Murray-related qualitative data
    print("\n  Searching broader Harvard Dataverse for qualitative data...")
    for query in ["qdpx qualitative", "interview transcript qualitative data"]:
        datasets = search_datasets(query, subtree="harvard", per_page=50)
        for ds in datasets:
            doi = ds.get("global_id")
            if doi and doi not in seen_dois:
                seen_dois[doi] = ds
        time.sleep(1)

    print(f"\n  Total unique datasets found: {len(seen_dois)}")

    if not seen_dois:
        print("  WARNING: No datasets found. The API may have changed.")
        print("  Check: https://dataverse.harvard.edu/api/search?q=qualitative&subtree=mra&type=dataset")
        return

    # Process each dataset
    processed = 0
    files_downloaded = 0

    for i, (doi, item) in enumerate(seen_dois.items(), 1):
        project_url = f"{DATAVERSE_URL}/dataset.xhtml?persistentId={doi}"

        if project_exists(project_url):
            print(f"  [{i}/{len(seen_dois)}] SKIP (already in DB): {doi}")
            continue

        print(f"\n  [{i}/{len(seen_dois)}] Processing: {doi}")

        meta = extract_metadata(item)
        print(f"  Title: {meta['title'][:60]}")

        now = datetime.utcnow().isoformat()
        # Use DOI as folder name (sanitize)
        folder_name = doi.replace("/", "_").replace(":", "_") if doi else f"harvard_{i}"

        project_data = {
            "query_string": "interview,qualitative,longitudinal",
            "repository_id": REPO_ID,
            "repository_url": REPO_URL,
            "project_url": project_url,
            "version": None,
            "title": meta["title"],
            "description": meta["description"],
            "language": meta["language"],
            "doi": meta["doi"],
            "upload_date": meta["upload_date"],
            "download_date": now,
            "download_repository_folder": REPO_FOLDER,
            "download_project_folder": folder_name,
            "download_version_folder": None,
            "download_method": "API-CALL",
        }

        project_id = insert_project(project_data)

        for kw in meta["keywords"]:
            insert_keyword(project_id, kw)
        for author in meta["authors"]:
            insert_person(project_id, author, ROLE_AUTHOR)
        insert_license(project_id, meta["license"])

        # Get and download files
        dest_folder = DATA_ROOT / REPO_FOLDER / folder_name
        file_list = get_dataset_files(doi) if doi else []

        if not file_list:
            insert_file(project_id, "no_files", "", STATUS_NO_DOWNLOAD_LINK)
        else:
            for file_info in file_list:
                df = file_info.get("dataFile", {})
                file_id = df.get("id")
                file_name = df.get("filename") or f"file_{file_id}"
                file_ext = Path(file_name).suffix.lower()
                ext = file_ext.lstrip(".")

                # Check if restricted
                restricted = file_info.get("restricted", False)
                if restricted:
                    insert_file(project_id, file_name, ext, STATUS_LOGIN_REQUIRED)
                    print(f"    [LOGIN_REQUIRED] {file_name}")
                    continue

                # Skip very large file types
                if file_ext in SKIP_EXTENSIONS:
                    print(f"    [SKIP large format] {file_name}")
                    insert_file(project_id, file_name, ext, "FAILED_NO_DOWNLOAD_LINK")
                    continue

                # Download
                file_url = f"{DATAVERSE_URL}/api/access/datafile/{file_id}"
                dest_path = dest_folder / file_name
                status = download_file(file_url, dest_path, extra_headers=HEADERS)
                insert_file(project_id, file_name, ext, status)

                if status == "SUCCEEDED":
                    files_downloaded += 1
                    print(f"    [SUCCEEDED] {file_name}")
                else:
                    print(f"    [{status}] {file_name}")

                time.sleep(0.5)

        processed += 1
        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"  Harvard scrape complete!")
    print(f"  New projects added: {processed}")
    print(f"  Files downloaded: {files_downloaded}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
