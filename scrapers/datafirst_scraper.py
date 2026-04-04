"""
DataFirst UCT Scraper (Repository #8) - Updated
-------------------------------------------------
This version also downloads freely available related materials
(PDF reports, questionnaires, metadata docs) from each study's
/related-materials page — no login required.

API for metadata: /api/catalog/{idno}
HTML for downloads: /catalog/{numeric_id}/related-materials
"""

import requests
import time
import re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from tqdm import tqdm

from db.database import (
    project_exists, insert_project, insert_file,
    insert_keyword, insert_person, insert_license,
    ROLE_AUTHOR, STATUS_NO_DOWNLOAD_LINK,
    STATUS_LOGIN_REQUIRED, STATUS_SUCCESS
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

HTML_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

SEARCH_QUERIES = [
    "interview",
    "qualitative",
    "qdpx",
    "transcript",
    "focus group",
]


def api_get(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [API ERROR] {url}: {e}")
        return None


def fetch_all_studies(query, page_size=100):
    studies = []
    page = 1
    while True:
        params = {"sk": query, "ps": page_size, "page": page}
        data = api_get(API_BASE, params=params)
        if not data:
            break
        result = data.get("result", data)
        rows = result.get("rows", [])
        if not rows:
            break
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
    url = f"{API_BASE}/{idno}"
    return api_get(url)


def get_numeric_id_from_idno(idno):
    """Get the numeric catalog ID by searching for the idno."""
    try:
        params = {"sk": idno, "ps": 5, "page": 1}
        data = api_get(API_BASE, params=params)
        if data:
            rows = data.get("result", {}).get("rows", [])
            for row in rows:
                if row.get("idno") == idno:
                    return row.get("id")
    except Exception:
        pass
    return None


def fetch_related_materials(numeric_id):
    """
    Scrape the /related-materials page to find free downloadable files.
    Returns list of {url, name, ext} dicts.
    """
    url = f"{BASE_URL}/catalog/{numeric_id}/related-materials"
    try:
        r = requests.get(url, headers=HTML_HEADERS, timeout=30)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "lxml")
        files = []
        # Find all download links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/download/" in href:
                # Make absolute URL
                if href.startswith("http"):
                    file_url = href
                else:
                    file_url = f"https://www.datafirst.uct.ac.za{href}"

                # Get filename from title attribute or link text
                file_name = a.get("title") or a.get_text(strip=True) or "download"
                # Clean up filename
                file_name = re.sub(r'\[.*?\]', '', file_name).strip()
                if not file_name or file_name == "Download":
                    # Try to get from URL
                    file_name = href.split("/")[-1] or f"file_{numeric_id}"

                ext = Path(file_name).suffix.lstrip(".").lower()
                if not ext:
                    ext = "pdf"  # most are PDFs
                    file_name = file_name + ".pdf"

                files.append({
                    "url": file_url,
                    "name": file_name,
                    "ext": ext
                })
        return files
    except Exception as e:
        print(f"  [MATERIALS ERROR] {url}: {e}")
        return []


def fetch_pdf_documentation(numeric_id):
    """Try to download the PDF documentation directly."""
    url = f"{BASE_URL}/catalog/{numeric_id}/pdf-documentation"
    return [{"url": url, "name": f"documentation_{numeric_id}.pdf", "ext": "pdf"}]


def extract_meta(detail, idno):
    study = (
        detail.get("dataset")
        or detail.get("study")
        or detail.get(idno)
        or detail
    )
    title = study.get("title") or study.get("name") or idno
    description = (
        study.get("abstract") or study.get("description") or study.get("notes") or ""
    )
    language = study.get("language") or study.get("lang") or "en"
    doi = study.get("doi") or study.get("doi_url") or None
    upload_date = (
        study.get("created") or study.get("date_created") or study.get("year_start") or None
    )
    authors = []
    for a in (study.get("authoring_entity") or study.get("authors") or []):
        name = a.get("name") if isinstance(a, dict) else str(a)
        if name and name.strip():
            authors.append(name.strip())
    keywords = []
    for kw in (study.get("keywords") or []):
        k = kw.get("keyword") if isinstance(kw, dict) else str(kw)
        if k and k.strip():
            keywords.append(k.strip())
    for topic in (study.get("topics") or []):
        k = topic.get("topic") if isinstance(topic, dict) else str(topic)
        if k and k.strip():
            keywords.append(k.strip())
    lic = (
        study.get("license") or study.get("access_conditions")
        or study.get("access_condition") or "Unknown"
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

    # Collect unique studies
    seen_idnos = {}
    for query in SEARCH_QUERIES:
        print(f"\n  Searching: '{query}'")
        studies = fetch_all_studies(query)
        for s in studies:
            idno = s["_idno"]
            if idno not in seen_idnos:
                seen_idnos[idno] = s
        time.sleep(1)

    print(f"\n  Found {len(seen_idnos)} unique studies.")

    for idno, row in tqdm(seen_idnos.items(), desc="  Processing studies"):
        project_url = f"{BASE_URL}/{idno}"

        if project_exists(project_url):
            continue

        detail = fetch_detail(idno)
        if detail:
            meta = extract_meta(detail, idno)
        else:
            meta = {
                "title": row.get("title") or idno,
                "description": row.get("abstract") or "",
                "language": row.get("language") or "en",
                "doi": row.get("doi") or None,
                "upload_date": row.get("created") or None,
                "authors": [],
                "keywords": [],
                "license": "Unknown",
            }

        # Get numeric ID from the row (needed for related-materials page)
        numeric_id = row.get("id") or row.get("nid")

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
        print(f"\n  [ADDED] {idno} — {meta['title'][:60]}")

        for kw in meta["keywords"]:
            insert_keyword(project_id, kw)
        for author in meta["authors"]:
            insert_person(project_id, author, ROLE_AUTHOR)
        insert_license(project_id, meta["license"])

        # Try to download related materials (free PDFs)
        dest_folder = data_root / REPO_FOLDER / idno
        files_found = False

        if numeric_id:
            materials = fetch_related_materials(numeric_id)
            if materials:
                files_found = True
                for f in materials:
                    dest_path = dest_folder / f["name"]
                    status = download_file(f["url"], dest_path, extra_headers=HTML_HEADERS)
                    insert_file(project_id, f["name"], f["ext"], status)
                    print(f"    [{status}] {f['name']}")
                    time.sleep(0.5)

            if not files_found:
                # Try PDF documentation
                pdf_files = fetch_pdf_documentation(numeric_id)
                for f in pdf_files:
                    dest_path = dest_folder / f["name"]
                    status = download_file(f["url"], dest_path, extra_headers=HTML_HEADERS)
                    if status == STATUS_SUCCESS:
                        files_found = True
                    insert_file(project_id, f["name"], f["ext"], status)
                    print(f"    [{status}] {f['name']}")

        if not files_found:
            insert_file(project_id, "no_files", "", STATUS_LOGIN_REQUIRED)

        time.sleep(1)

    print(f"\n  DataFirst scrape complete.")