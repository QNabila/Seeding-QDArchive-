"""
DataFirst UCT Scraper (Repository #8)
--------------------------------------
DataFirst runs on NADA/IHSN software with a JSON API.

IMPORTANT: The catalog list returns numeric IDs but the detail endpoint
uses 'idno' string identifiers (e.g. "ZAF-DATAFIRST-001-2003-v1").
We must extract 'idno' from the list response, not use numeric IDs.

API:
  GET /api/catalog?sk=interview&ps=100&page=1  -> list with idno field
  GET /api/catalog/{idno}                       -> detail for one study
  GET /api/catalog/{idno}/resources             -> downloadable files
"""

import requests
import time
from datetime import datetime
from pathlib import Path
from tqdm import tqdm

from db.database import (
    project_exists, insert_project, insert_file,
    insert_keyword, insert_person, insert_license,
    ROLE_AUTHOR, ROLE_UNKNOWN, STATUS_NO_DOWNLOAD_LINK,
    STATUS_LOGIN_REQUIRED
)
from pipeline.downloader import download_file

REPO_ID = 1
REPO_URL = "https://datafirst.uct.ac.za"
BASE_URL = "https://www.datafirst.uct.ac.za/dataportal/index.php"
API_BASE = f"{BASE_URL}/api/catalog"
REPO_FOLDER = "datafirst"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Search queries — professor recommends qdpx, interview study, qualitative
SEARCH_QUERIES = [
    "interview",
    "qualitative",
    "qdpx",
    "transcript",
    "focus group",
]


def api_get(url, params=None):
    """Make an API GET request."""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [API ERROR] {url}: {e}")
        return None


def fetch_all_studies(query, page_size=100):
    """Fetch all studies for a query, returning list of study dicts with idno."""
    studies = []
    page = 1

    while True:
        params = {"sk": query, "ps": page_size, "page": page}
        data = api_get(API_BASE, params=params)

        if not data:
            break

        # Handle both response shapes NADA can return
        result = data.get("result", data)
        rows = result.get("rows", [])

        if not rows:
            break

        # Only keep studies that have an idno (string identifier)
        for row in rows:
            idno = row.get("idno") or row.get("id_no") or row.get("study_idno")
            if idno:
                row["_idno"] = str(idno)
                studies.append(row)

        total = result.get("found", 0)
        print(f"    Query '{query}' page {page}: {len(rows)} results (total: {total})")

        if len(studies) >= int(total) or len(rows) < page_size:
            break

        page += 1
        time.sleep(0.5)

    return studies


def fetch_detail(idno):
    """Fetch full metadata using the idno string."""
    url = f"{API_BASE}/{idno}"
    return api_get(url)


def fetch_resources(idno):
    """Fetch downloadable files for a study."""
    url = f"{API_BASE}/{idno}/resources"
    data = api_get(url)
    if not data:
        return []
    # Resources can be under different keys
    return (
        data.get("resources", [])
        or data.get("files", [])
        or data.get("data_files", [])
        or []
    )


def extract_meta(detail, idno):
    """Pull clean metadata out of a detail response."""
    # The actual study data may be nested
    study = (
        detail.get("dataset")
        or detail.get("study")
        or detail.get(idno)
        or detail
    )

    title = (
        study.get("title")
        or study.get("name")
        or idno
    )

    description = (
        study.get("abstract")
        or study.get("description")
        or study.get("notes")
        or ""
    )

    language = study.get("language") or study.get("lang") or "en"
    doi = study.get("doi") or study.get("doi_url") or None

    upload_date = (
        study.get("created")
        or study.get("date_created")
        or study.get("year_start")
        or None
    )

    # Authors
    authors = []
    for a in (study.get("authoring_entity") or study.get("authors") or []):
        if isinstance(a, dict):
            name = a.get("name") or a.get("affiliation") or ""
        else:
            name = str(a)
        if name.strip():
            authors.append(name.strip())

    # Keywords — store raw as professor instructs
    keywords = []
    for kw in (study.get("keywords") or []):
        if isinstance(kw, dict):
            k = kw.get("keyword") or kw.get("name") or ""
        else:
            k = str(kw)
        if k.strip():
            keywords.append(k.strip())
    for topic in (study.get("topics") or []):
        if isinstance(topic, dict):
            k = topic.get("topic") or topic.get("name") or ""
        else:
            k = str(topic)
        if k.strip():
            keywords.append(k.strip())

    # License
    lic = (
        study.get("license")
        or study.get("access_conditions")
        or study.get("access_condition")
        or "Unknown"
    )
    if isinstance(lic, list):
        lic = "; ".join(str(x) for x in lic)

    return {
        "title": str(title)[:500],
        "description": str(description)[:2000],
        "language": str(language)[:20],
        "doi": str(doi) if doi else None,
        "upload_date": str(upload_date)[:20] if upload_date else None,
        "authors": authors,
        "keywords": keywords,
        "license": str(lic)[:200],
    }


def run(data_root: Path):
    """Main entry point."""
    print("\n=== DataFirst UCT Scraper ===")

    # Step 1: collect unique idno values across all search queries
    seen_idnos = {}  # idno -> row dict

    for query in SEARCH_QUERIES:
        print(f"\n  Searching: '{query}'")
        studies = fetch_all_studies(query)
        for s in studies:
            idno = s["_idno"]
            if idno not in seen_idnos:
                seen_idnos[idno] = s
        time.sleep(1)

    print(f"\n  Found {len(seen_idnos)} unique studies.")

    if not seen_idnos:
        print("  WARNING: No studies found. The API may have changed.")
        print("  Tip: Try visiting https://www.datafirst.uct.ac.za/dataportal/index.php/api/catalog?sk=interview")
        print("  in your browser to check what the API returns.")
        return

    # Step 2: process each study
    for idno, row in tqdm(seen_idnos.items(), desc="  Processing studies"):

        project_url = f"{BASE_URL}/{idno}"

        if project_exists(project_url):
            continue

        # Try to get full detail; fall back to list row data
        detail = fetch_detail(idno)
        if detail:
            meta = extract_meta(detail, idno)
        else:
            # Use what we have from the list row
            meta = {
                "title": row.get("title") or idno,
                "description": row.get("abstract") or row.get("description") or "",
                "language": row.get("language") or "en",
                "doi": row.get("doi") or None,
                "upload_date": row.get("created") or None,
                "authors": [],
                "keywords": [],
                "license": "Unknown",
            }

        now = datetime.utcnow().isoformat()
        project_data = {
            "query_string": "interview,qualitative,qdpx",
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
            "download_project_folder": idno,
            "download_version_folder": None,
            "download_method": "API-CALL",
        }

        project_id = insert_project(project_data)
        print(f"  [ADDED] {idno} — {meta['title'][:60]}")

        for kw in meta["keywords"]:
            insert_keyword(project_id, kw)

        for author in meta["authors"]:
            insert_person(project_id, author, ROLE_AUTHOR)

        insert_license(project_id, meta["license"])

        # Try to download files
        resources = fetch_resources(idno)
        dest_folder = data_root / REPO_FOLDER / idno

        if not resources:
            insert_file(project_id, "no_files", "", STATUS_NO_DOWNLOAD_LINK)
        else:
            for res in resources:
                file_url = (
                    res.get("uri") or res.get("url")
                    or res.get("download_url") or res.get("link")
                )
                file_name = (
                    res.get("title") or res.get("filename")
                    or res.get("name") or "unknown_file"
                )
                file_name = str(file_name).replace("/", "_")
                ext = Path(file_name).suffix.lstrip(".").lower()

                access = str(res.get("access") or res.get("type") or "").lower()
                if "licensed" in access or "restricted" in access:
                    insert_file(project_id, file_name, ext, STATUS_LOGIN_REQUIRED)
                    continue

                if not file_url:
                    insert_file(project_id, file_name, ext, STATUS_NO_DOWNLOAD_LINK)
                    continue

                dest_path = dest_folder / file_name
                status = download_file(file_url, dest_path, extra_headers=HEADERS)
                insert_file(project_id, file_name, ext, status)
                print(f"    [{status}] {file_name}")

        time.sleep(1)

    print(f"\n  DataFirst scrape complete.")