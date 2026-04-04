"""
Harvard Murray Archive Scraper (Repository #18)
-------------------------------------------------
The Murray Research Archive at Harvard is a collection of social science
datasets and interview studies. It is a static HTML site — no public JSON API.

We scrape the catalog pages using BeautifulSoup to find study listings,
then visit each study page to extract metadata and download files.

Base URL: https://www.murray.harvard.edu
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
    ROLE_AUTHOR, ROLE_UNKNOWN, STATUS_NO_DOWNLOAD_LINK,
    STATUS_LOGIN_REQUIRED
)
from pipeline.downloader import download_file

REPO_ID = 2
REPO_URL = "https://www.murray.harvard.edu"
REPO_FOLDER = "harvard"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Known catalog / listing pages on Murray Archive
CATALOG_PAGES = [
    "https://www.murray.harvard.edu/",
    "https://www.murray.harvard.edu/index.html",
]

# File types we want to download
DOWNLOAD_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".rtf",
    ".xlsx", ".xls", ".csv",
    ".mp3", ".mp4", ".wav",
    ".zip", ".7z"
}


def get_page(url):
    """Fetch and parse an HTML page. Returns BeautifulSoup or None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "lxml")
        elif r.status_code in (401, 403):
            print(f"  [ACCESS DENIED] {url}")
            return None
        else:
            print(f"  [HTTP {r.status_code}] {url}")
            return None
    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return None


def find_study_links(soup, base_url):
    """Extract links to individual study pages from a catalog page."""
    links = set()
    if not soup:
        return links

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Make absolute URL
        if href.startswith("http"):
            full_url = href
        elif href.startswith("/"):
            full_url = REPO_URL + href
        else:
            full_url = base_url.rstrip("/") + "/" + href

        # Only follow links within the same domain
        if "murray.harvard.edu" in full_url:
            links.add(full_url)

    return links


def extract_study_metadata(url, soup):
    """Extract metadata from a study detail page."""
    if not soup:
        return None

    # Title — try common HTML patterns
    title = None
    for selector in ["h1", "h2", ".study-title", ".title", "title"]:
        tag = soup.find(selector)
        if tag and tag.get_text(strip=True):
            title = tag.get_text(strip=True)
            break
    if not title:
        title = url.split("/")[-1] or "Untitled"

    # Description — try meta description, first paragraph, or div.abstract
    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"]
    else:
        for selector in [".abstract", ".description", "p"]:
            tag = soup.find(selector)
            if tag and len(tag.get_text(strip=True)) > 20:
                description = tag.get_text(strip=True)[:2000]
                break

    # Authors
    authors = []
    for selector in [".author", ".creator", "[rel='author']"]:
        for tag in soup.find_all(selector):
            name = tag.get_text(strip=True)
            if name:
                authors.append(name)

    # Keywords
    keywords = []
    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    if meta_keywords and meta_keywords.get("content"):
        keywords = [k.strip() for k in meta_keywords["content"].split(",") if k.strip()]

    # Find all downloadable file links
    file_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        ext = Path(href.split("?")[0]).suffix.lower()
        if ext in DOWNLOAD_EXTENSIONS:
            if href.startswith("http"):
                file_url = href
            elif href.startswith("/"):
                file_url = REPO_URL + href
            else:
                file_url = url.rstrip("/") + "/" + href
            file_name = a.get_text(strip=True) or Path(href).name or "file" + ext
            file_links.append({"url": file_url, "name": file_name, "ext": ext.lstrip(".")})

    # Study ID from URL
    study_id = re.sub(r"[^a-zA-Z0-9_-]", "_", url.split("murray.harvard.edu")[-1].strip("/"))
    if not study_id:
        study_id = "root"

    return {
        "title": title[:500],
        "description": description[:2000],
        "authors": authors,
        "keywords": keywords,
        "license": "Unknown",
        "study_id": study_id,
        "file_links": file_links,
    }


def run(data_root: Path):
    """Main entry point — scrape Harvard Murray Archive."""
    print("\n=== Harvard Murray Archive Scraper ===")

    # Step 1: collect all study URLs by crawling catalog pages
    visited = set()
    study_urls = set()

    print("  Crawling catalog pages...")
    for catalog_url in CATALOG_PAGES:
        soup = get_page(catalog_url)
        if soup:
            links = find_study_links(soup, catalog_url)
            study_urls.update(links)
            visited.add(catalog_url)
            time.sleep(1)

    # Filter: only pages that look like study/dataset pages (not nav/external)
    # Keep all murray.harvard.edu pages found
    study_urls -= visited  # don't re-process catalog pages we already crawled

    print(f"  Found {len(study_urls)} candidate pages to inspect.")

    if not study_urls:
        # Fallback: record the site itself with a note
        print("  WARNING: No study pages found. The site may block automated access.")
        print("  Recording root page as FAILED_LOGIN_REQUIRED.")

        if not project_exists(REPO_URL):
            now = datetime.utcnow().isoformat()
            project_data = {
                "query_string": "qualitative interview",
                "repository_id": REPO_ID,
                "repository_url": REPO_URL,
                "project_url": REPO_URL,
                "version": None,
                "title": "Murray Research Archive (Harvard) — Access Blocked",
                "description": (
                    "The Murray Research Archive at Harvard Dataverse contains "
                    "longitudinal social science studies and interview datasets. "
                    "Automated access was blocked during scraping — manual access "
                    "may require registration at the Harvard Dataverse portal."
                ),
                "language": "en",
                "doi": None,
                "upload_date": None,
                "download_date": now,
                "download_repository_folder": REPO_FOLDER,
                "download_project_folder": "murray_archive",
                "download_version_folder": None,
                "download_method": "SCRAPING",
            }
            project_id = insert_project(project_data)
            insert_keyword(project_id, "qualitative")
            insert_keyword(project_id, "longitudinal")
            insert_keyword(project_id, "social science")
            insert_person(project_id, "Murray Research Archive", ROLE_OWNER)
            insert_license(project_id, "Harvard Dataverse Terms of Use")
            insert_file(project_id, "site_blocked", "", "FAILED_LOGIN_REQUIRED")
            print("  Recorded blocked access in database.")
        return

    # Step 2: process each study page
    processed = 0
    for url in tqdm(study_urls, desc="  Scraping study pages"):
        if project_exists(url):
            continue

        soup = get_page(url)
        if not soup:
            continue

        meta = extract_study_metadata(url, soup)
        if not meta:
            continue

        now = datetime.utcnow().isoformat()
        project_data = {
            "query_string": "qualitative interview",
            "repository_id": REPO_ID,
            "repository_url": REPO_URL,
            "project_url": url,
            "version": None,
            "title": meta["title"],
            "description": meta["description"],
            "language": "en",
            "doi": None,
            "upload_date": None,
            "download_date": now,
            "download_repository_folder": REPO_FOLDER,
            "download_project_folder": meta["study_id"],
            "download_version_folder": None,
            "download_method": "SCRAPING",
        }

        project_id = insert_project(project_data)

        for kw in meta["keywords"]:
            insert_keyword(project_id, kw)
        for author in meta["authors"]:
            insert_person(project_id, author, ROLE_AUTHOR)
        insert_license(project_id, meta["license"])

        # Download files
        dest_folder = data_root / REPO_FOLDER / meta["study_id"]
        if not meta["file_links"]:
            insert_file(project_id, "no_files", "", STATUS_NO_DOWNLOAD_LINK)
        else:
            for f in meta["file_links"]:
                dest_path = dest_folder / f["name"]
                status = download_file(f["url"], dest_path)
                insert_file(project_id, f["name"], f["ext"], status)
                print(f"    [{status}] {f['name']}")

        processed += 1
        time.sleep(2)

    print(f"\n  Harvard scrape complete. Processed {processed} pages.")
