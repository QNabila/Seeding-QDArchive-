"""
DataFirst Full Catalog Crawler
--------------------------------
Crawls ALL 596 studies from DataFirst (no keyword filter)
and downloads their related materials.

Run with:
    python3 scripts/crawl_all_datafirst.py
"""

import sys
import requests
import time
import re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import (
    project_exists, insert_project, insert_file,
    insert_keyword, insert_person, insert_license,
    ROLE_AUTHOR, STATUS_NO_DOWNLOAD_LINK, STATUS_LOGIN_REQUIRED
)
from pipeline.downloader import download_file

BASE_URL = "https://www.datafirst.uct.ac.za/dataportal/index.php"
API_BASE = f"{BASE_URL}/api/catalog"
REPO_ID = 1
REPO_URL = "https://datafirst.uct.ac.za"
REPO_FOLDER = "datafirst"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

HTML_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

DATA_ROOT = Path(__file__).parent.parent / "data"


def fetch_all_studies():
    """Fetch every study from DataFirst with no keyword filter."""
    all_studies = {}
    page = 1
    while True:
        try:
            r = requests.get(
                API_BASE,
                headers=HEADERS,
                params={"ps": 100, "page": page},
                timeout=30
            )
            data = r.json()
            rows = data.get("result", {}).get("rows", [])
            if not rows:
                break
            for row in rows:
                idno = row.get("idno")
                if idno:
                    all_studies[str(idno)] = row
            total = int(data.get("result", {}).get("found", 0))
            print(f"  Page {page}: {len(rows)} studies (total: {total}, collected: {len(all_studies)})")
            if len(all_studies) >= total or len(rows) < 100:
                break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break
    return all_studies


def fetch_detail(idno):
    """Fetch full metadata for a study."""
    try:
        r = requests.get(f"{API_BASE}/{idno}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [API ERROR] {idno}: {e}")
        return None


def fetch_related_materials(numeric_id):
    """Scrape free downloadable files from the related-materials page."""
    url = f"{BASE_URL}/catalog/{numeric_id}/related-materials"
    try:
        r = requests.get(url, headers=HTML_HEADERS, timeout=30)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "lxml")
        files = []
        seen_urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/download/" not in href:
                continue
            if href.startswith("http"):
                file_url = href
            else:
                file_url = f"https://www.datafirst.uct.ac.za{href}"
            if file_url in seen_urls:
                continue
            seen_urls.add(file_url)
            file_name = a.get("title") or a.get_text(strip=True) or "download"
            file_name = re.sub(r'\[.*?\]', '', file_name).strip()
            if not file_name or file_name.lower() == "download":
                file_name = href.split("/")[-1] or f"file_{numeric_id}"
            ext = Path(file_name).suffix.lstrip(".").lower()
            if not ext:
                ext = "pdf"
                file_name = file_name + ".pdf"
            files.append({"url": file_url, "name": file_name, "ext": ext})
        return files
    except Exception as e:
        print(f"  [MATERIALS ERROR] {url}: {e}")
        return []


def extract_meta(detail, idno, row):
    """Extract metadata from API detail response."""
    study = (
        detail.get("dataset") or detail.get("study") or detail
        if detail else {}
    )

    title = study.get("title") or row.get("title") or idno
    description = (
        study.get("abstract") or study.get("description") or
        study.get("notes") or row.get("subtitle") or ""
    )
    language = study.get("language") or "en"
    doi = study.get("doi") or row.get("doi") or None
    upload_date = (
        study.get("created") or row.get("created") or
        str(row.get("year_start")) if row.get("year_start") else None
    )

    authors = []
    authoring = (
        study.get("authoring_entity") or
        [{"name": row.get("authoring_entity")}] if row.get("authoring_entity") else []
    )
    for a in authoring:
        name = a.get("name") if isinstance(a, dict) else str(a)
        if name and name.strip():
            authors.append(name.strip())

    keywords = []
    for kw in (study.get("keywords") or []):
        k = kw.get("keyword") if isinstance(kw, dict) else str(kw)
        if k and k.strip():
            keywords.append(k.strip())

    # License
    lic = (
        study.get("license") or study.get("access_conditions") or
        study.get("access_condition") or "CC BY"
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


def main():
    print("=" * 50)
    print("  DataFirst Full Catalog Crawler")
    print("=" * 50)

    # Step 1: Get all studies
    print("\nFetching full catalog...")
    all_studies = fetch_all_studies()
    print(f"\nTotal studies in DataFirst: {len(all_studies)}")

    # Step 2: Find new ones
    new_studies = {
        idno: row for idno, row in all_studies.items()
        if not project_exists(f"{BASE_URL}/{idno}")
    }
    print(f"Already in database: {len(all_studies) - len(new_studies)}")
    print(f"New studies to process: {len(new_studies)}")

    if not new_studies:
        print("Nothing new to download!")
        return

    # Step 3: Process each new study
    success_count = 0
    file_count = 0

    for i, (idno, row) in enumerate(new_studies.items(), 1):
        print(f"\n[{i}/{len(new_studies)}] {idno}")

        project_url = f"{BASE_URL}/{idno}"
        numeric_id = row.get("id")

        # Fetch detail
        detail = fetch_detail(idno)
        meta = extract_meta(detail, idno, row)

        print(f"  Title: {meta['title'][:60]}")

        # Insert project
        now = datetime.utcnow().isoformat()
        project_data = {
            "query_string": "full_catalog_crawl",
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

        for kw in meta["keywords"]:
            insert_keyword(project_id, kw)
        for author in meta["authors"]:
            insert_person(project_id, author, ROLE_AUTHOR)
        insert_license(project_id, meta["license"])

        # Download related materials
        dest_folder = DATA_ROOT / REPO_FOLDER / idno
        files_downloaded = 0

        if numeric_id:
            materials = fetch_related_materials(numeric_id)
            if materials:
                for f in materials:
                    dest_path = dest_folder / f["name"]
                    status = download_file(f["url"], dest_path, extra_headers=HTML_HEADERS)
                    insert_file(project_id, f["name"], f["ext"], status)
                    if status == "SUCCEEDED":
                        files_downloaded += 1
                        file_count += 1
                        print(f"  [SUCCEEDED] {f['name']}")
                    else:
                        print(f"  [{status}] {f['name']}")
                    time.sleep(0.3)
            else:
                insert_file(project_id, "no_files", "", STATUS_LOGIN_REQUIRED)

        success_count += 1
        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"  Crawl complete!")
    print(f"  New projects added: {success_count}")
    print(f"  New files downloaded: {file_count}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
