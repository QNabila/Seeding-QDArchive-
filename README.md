# QDArchive — Part 1: Data Acquisition Pipeline

**Student:** Nabila Kader | **Student ID:** 23079506
**Course:** Seeding QDArchive (SQ26) — Applied Software Engineering
**University:** FAU Erlangen-Nürnberg
**Professor:** Dirk Riehle, Professorship for Open-Source Software
**Semester:** Winter 2025/26 + Summer 2026
**Submission Tag:** `part-1-release`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Assigned Repositories](#2-assigned-repositories)
3. [Final Results](#3-final-results)
4. [Repository Structure](#4-repository-structure)
5. [Database Schema](#5-database-schema)
6. [How to Run](#6-how-to-run)
7. [Scraping Strategy](#7-scraping-strategy)
8. [Search Queries Used](#8-search-queries-used)
9. [Download Strategy](#9-download-strategy)
10. [Data Quality Notes](#10-data-quality-notes)
11. [Technical Challenges](#11-technical-challenges)
12. [Submission Checklist](#12-submission-checklist)

---

## 1. Project Overview

QDArchive is a web service for researchers to publish and archive qualitative data, with an emphasis on Qualitative Data Analysis (QDA) files. The goal of Part 1 is to **seed QDArchive** by building an automated data acquisition pipeline that:

- Scrapes qualitative research projects from assigned public repositories
- Downloads all publicly available files
- Stores structured metadata in a SQLite database following the professor's exact schema
- Exports all data to CSV format
- Reports clearly on what was downloaded and what could not be downloaded (with reasons)

---

## 2. Assigned Repositories

| # | Name | URL | Type |
|---|------|-----|------|
| 8 | DataFirst UCT | https://datafirst.uct.ac.za | JSON API + HTML |
| 18 | Harvard Murray Archive | https://www.murray.harvard.edu | HTML + Harvard Dataverse API |

---

## 3. Final Results

### Summary Statistics

| Metric | Value |
|--------|-------|
| **Total projects collected** | **1,518** |
| DataFirst UCT projects | 596 (full catalog) |
| Harvard Dataverse projects | 922 |
| **Files successfully downloaded** | **9,989** |
| Files requiring login (correctly recorded) | 11,198 |
| Keywords collected | 1,727 |
| Person / author records | 24,757 |
| License records | 1,518 |
| Total data on disk | ~2.8 GB |

### File Download Status Breakdown

| Status | Count | Meaning |
|--------|-------|---------|
| `SUCCEEDED` | 9,989 | File downloaded successfully |
| `FAILED_LOGIN_REQUIRED` | 11,198 | File requires institutional login — correctly recorded |
| `FAILED_NO_DOWNLOAD_LINK` | 19 | No downloadable file found for this project |
| `FAILED_HTTP_ERROR` | 19 | Server returned an HTTP error |
| `FAILED_SERVER_UNRESPONSIVE` | 6 | Server did not respond |
| `FAILED_TIMEOUT` | 1 | Request timed out |

### File Types Downloaded

| Extension | Count | Description |
|-----------|-------|-------------|
| `.pdf` | 1,194 | Reports, questionnaires, codebooks, metadata |
| `.zip` | 75 | Instrument packages, program files, codebooks |
| `.xlsx` | 22 | Excel spreadsheets, codebooks |
| `.xls` | 9 | Legacy Excel files |
| `.ppt` | 2 | Presentations |
| `.doc` | 2 | Word documents |
| `.txt` | 1 | Text files |
| `.docx` | 1 | Word document |
| `.do` | 1 | Stata do-file |

### Qualitative Research Materials Found

Although neither repository hosts `.qdpx` or QDA software files (they are survey/statistics archives, not QDA repositories), the following qualitative research materials were successfully downloaded:

| Type | Examples |
|------|---------|
| Interview instruments | `fpoi-2014-2015-interview-instrument.pdf`, `oerm-2015-2016-interview-instrument.pdf` |
| Interview schedules | `rscaoersa-2015-interview-schedule.pdf` |
| Interview documents | `ecdc-2021-interview.pdf`, `Interviewer Manual.pdf` |
| Codebooks (40+) | SASAS 2003–2012 codebooks, Afrobarometer codebooks, NIDS codebooks |
| Survey questionnaires (200+) | Labour Force Survey, General Household Survey, Victims of Crime Survey |
| Research reports (500+) | Statistical releases, technical reports |
| Data documentation (ZIP) | Instrument packages, program files |

---

## 4. Repository Structure

```
Seeding-QDArchive-/
├── 23079506-seeding.db              ← SQLite database (professor's required naming)
├── README.md                        ← This file
├── .gitignore                       ← Excludes metadata.db, data/, .env
├── requirements.txt                 ← Python dependencies
├── main.py                          ← Main entry point
│
├── db/
│   ├── __init__.py
│   ├── schema.sql                   ← Creates all 6 tables + seeds repositories
│   └── database.py                  ← DB functions, status/role constants
│
├── scrapers/
│   ├── __init__.py
│   ├── datafirst_scraper.py         ← DataFirst UCT keyword search scraper
│   └── harvard_scraper.py           ← Harvard Murray website HTML scraper
│
├── pipeline/
│   ├── __init__.py
│   └── downloader.py                ← HTTP file downloader with status tracking
│
├── export/
│   ├── __init__.py
│   ├── csv_exporter.py              ← Exports all 6 tables to CSV
│   └── csv/
│       ├── repositories.csv         ← 2 rows
│       ├── projects.csv             ← 1,518 rows
│       ├── files.csv                ← 21,232 rows
│       ├── keywords.csv             ← 1,727 rows
│       ├── person_role.csv          ← 24,757 rows
│       └── licenses.csv             ← 1,518 rows
│
├── scripts/
│   ├── retry_429.py                 ← Retries HTTP 429 rate-limited downloads
│   ├── crawl_all_datafirst.py       ← Full catalog crawl (all 596 studies)
│   └── harvard_dataverse_scraper.py ← Harvard Dataverse API scraper
│
└── data/                            ← NOT in Git — on Google Drive
    ├── datafirst/{project_idno}/    ← e.g. datafirst/zaf-statssa-dts-2021-v1/
    └── harvard/{doi_as_folder}/     ← e.g. harvard/doi_10.7910_DVN_XXXXX/
```

---

## 5. Database Schema

The database `23079506-seeding.db` follows the professor's exact schema with 6 tables.

### REPOSITORIES
Seed table for the two assigned repositories.

| Field | Type | Value |
|-------|------|-------|
| id | INTEGER | 1 = datafirst, 2 = harvard |
| name | TEXT | `datafirst` / `harvard` |
| url | TEXT | Top-level repo URL |

### PROJECTS
One row per research project. All required fields are populated.

| Field | Type | Notes |
|-------|------|-------|
| id | INTEGER | Auto-increment primary key |
| query_string | STRING | Query that found this project |
| repository_id | INTEGER | FK → REPOSITORIES |
| repository_url | URL | Top-level repo URL |
| project_url | URL | Full URL to project page |
| version | STRING | Version string if any |
| title | STRING | Project title |
| description | TEXT | Abstract / description |
| language | BCP 47 | e.g. `en` |
| doi | URL | DOI URL if available |
| upload_date | DATE | Upload date from source |
| download_date | TIMESTAMP | When our download concluded |
| download_repository_folder | STRING | e.g. `datafirst` |
| download_project_folder | STRING | Project ID from source site |
| download_version_folder | STRING | NULL (see Data Quality Notes) |
| download_method | ENUM | `API-CALL` or `SCRAPING` |

### FILES
One row per file per project — both successful and failed downloads.

| Field | Type | Notes |
|-------|------|-------|
| id | INTEGER | Auto-increment primary key |
| project_id | INTEGER | FK → PROJECTS |
| file_name | STRING | Filename as on source site |
| file_type | STRING | Extension only (e.g. `pdf`) |
| status | DOWNLOAD_RESULT | See enum values below |

**DOWNLOAD_RESULT enum values used:**
- `SUCCEEDED` — file downloaded successfully
- `FAILED_LOGIN_REQUIRED` — institutional registration required
- `FAILED_SERVER_UNRESPONSIVE` — server did not respond (HTTP 500)
- `FAILED_NO_DOWNLOAD_LINK` — no downloadable file found
- `FAILED_HTTP_ERROR` — other HTTP error
- `FAILED_TIMEOUT` — request timed out

### KEYWORDS
One row per keyword per project.

| Field | Notes |
|-------|-------|
| project_id | FK → PROJECTS |
| keyword | Raw keyword string from source |

*Note: DataFirst does not return keywords in their API for most studies. Harvard Dataverse keywords are captured where available. See Data Quality Notes.*

### PERSON_ROLE
One row per person per project — 24,757 records.

| Field | Notes |
|-------|-------|
| name | Full name string |
| role | `AUTHOR`, `UPLOADER`, `OWNER`, `OTHER`, or `UNKNOWN` |

### LICENSES
One row per license per project — 1,518 records.

| Field | Notes |
|-------|-------|
| license | e.g. `CC BY`, `CC0`, `CC BY-SA` |

---

## 6. How to Run

### Prerequisites
- Python 3.9+
- macOS / Linux
- Internet connection

### Setup
```bash
# Clone the repository
git clone https://github.com/QNabila/Seeding-QDArchive-.git
cd Seeding-QDArchive-

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run the Main Pipeline
```bash
# Run both scrapers + export (full pipeline)
python3 main.py

# Run only DataFirst keyword scraper
python3 main.py --source datafirst

# Run only Harvard Murray HTML scraper
python3 main.py --source harvard

# Check database statistics
python3 main.py --stats

# Export all tables to CSV only
python3 main.py --export
```

### Run Additional Scripts
```bash
# Crawl ALL 596 DataFirst studies (not just keyword results)
python3 scripts/crawl_all_datafirst.py

# Scrape Harvard Dataverse via API
python3 scripts/harvard_dataverse_scraper.py

# Retry rate-limited (HTTP 429) downloads
python3 scripts/retry_429.py
```

### Expected Runtime
| Script | Time |
|--------|------|
| `main.py --source datafirst` | ~18 minutes (313 studies) |
| `crawl_all_datafirst.py` | ~45–60 minutes (596 studies) |
| `harvard_dataverse_scraper.py` | ~20–30 minutes |

---

## 7. Scraping Strategy

### Two Approaches Used (as per professor's guidelines)

**Approach 1 — Query-based search (original default)**
Used for `main.py` with DataFirst. Searches using specific queries (`interview`, `qualitative`, `qdpx`, etc.) via the NADA JSON API.

**Approach 2 — Full catalog crawl**
Used for `crawl_all_datafirst.py`. Fetches all studies from DataFirst with no keyword filter, using pagination (`ps=100&page=N`). This captured all 596 studies including those not matching keyword queries.

**Approach 3 — API-based scraping**
Used for `harvard_dataverse_scraper.py`. Uses the Harvard Dataverse public REST API (`/api/search` and `/api/datasets/:persistentId/versions/:version/files`) to collect datasets and download public files.

---

## 8. Search Queries Used

### DataFirst UCT

| Query | Studies Found |
|-------|--------------|
| `interview` | 301 |
| `qualitative` | 28 |
| `qdpx` | 0 |
| `transcript` | 3 |
| `focus group` | 28 |
| *(full catalog crawl — no query)* | 596 total |

### Harvard Dataverse (Murray Archive)

| Query | Subtree |
|-------|---------|
| `interview` | `mra` (Murray Research Archive) |
| `qualitative` | `mra` |
| `longitudinal` | `mra` |
| `oral history` | `mra` |
| `life study` | `mra` |
| `survey` | `mra` |
| `qdpx qualitative` | `harvard` (broader) |
| `interview transcript qualitative data` | `harvard` (broader) |

---

## 9. Download Strategy

### DataFirst UCT

DataFirst uses NADA/IHSN platform software. Two layers of data are accessible:

**Layer 1 — Metadata (free, via JSON API)**
All 596 studies have metadata freely accessible via `GET /api/catalog/{idno}`. This includes title, description, authors, language, DOI, upload date, and access conditions.

**Layer 2 — Related Materials (free, via HTML scraping)**
Each study has a `/related-materials` page containing downloadable PDFs, Excel files, and ZIP archives. These include:
- Survey questionnaires
- Statistical release reports
- Metadata documentation
- Codebooks
- Program files

These were discovered by scraping the HTML page and downloading each linked file.

**Layer 3 — Microdata (login required)**
The actual SPSS/Stata microdata files require institutional registration at DataFirst. These are correctly recorded as `FAILED_LOGIN_REQUIRED`.

### Harvard Murray Archive / Harvard Dataverse

The Harvard Murray Archive website (`murray.harvard.edu`) is a landing page only. The actual datasets are hosted on Harvard Dataverse at `dataverse.harvard.edu/dataverse/mra`.

**Harvard Dataverse Public API** (no login required):
- `GET /api/search?q={query}&subtree=mra&type=dataset` — search datasets
- `GET /api/datasets/:persistentId/versions/:version/files` — list files
- `GET /api/access/datafile/{id}` — download individual files

Public (unrestricted) files are downloaded directly. Restricted files are recorded as `FAILED_LOGIN_REQUIRED`.

---

## 10. Data Quality Notes

The professor's stated rule: *"Do not change data when downloading; data quality issues will be resolved in a second step."*

### Issue 1: Keywords Missing for DataFirst Studies
DataFirst's NADA API does not include keyword fields in their JSON metadata responses for the majority of studies. The `KEYWORDS` table is populated only for Harvard Dataverse datasets where keywords were available in the API response. This is a source repository data quality issue.

### Issue 2: Harvard Murray Website Has Minimal Content
The `murray.harvard.edu` website is an institutional landing page with only ~9 navigable pages. All actual research data is on Harvard Dataverse. The HTML scraper correctly handles this and the Dataverse API scraper was added to collect proper data.

### Issue 3: Duplicate File Entries (Fixed)
Some DataFirst related-materials pages listed the same file multiple times under different sections. A deduplication query was applied after scraping:
```sql
DELETE FROM FILES WHERE id NOT IN (
    SELECT MIN(id) FROM FILES
    GROUP BY project_id, file_name, file_type
);
```
1,318 duplicates were removed.

### Issue 4: Version Folder NULL
The `download_version_folder` field is NULL for all records. DataFirst encodes version in the `idno` string (e.g. `v1` in `zaf-statssa-dts-2021-v1`). Harvard Dataverse uses versioned dataset DOIs. Extracting explicit version subfolders is a data quality improvement for a future step.

### Issue 5: Status Enum Normalization
The initial scraper used `SUCCESS` instead of `SUCCEEDED`. All records were normalized to `SUCCEEDED` to match the professor's DOWNLOAD_RESULT enum.

### Issue 6: License Values
DataFirst states "Creative Commons CC-BY (Attribution-only) License" in access conditions — stored as `CC BY`. Harvard Dataverse datasets use `CC0` by default — stored as `CC0` where detected.

---

## 11. Technical Challenges

### Challenge 1: DataFirst API Returns HTTP 400 for All Numeric IDs

**Problem:** The initial scraper called `/api/catalog/193`, `/api/catalog/231` etc. using numeric IDs — every single one returned HTTP 400 Bad Request.

**Root cause:** DataFirst's NADA API uses string `idno` identifiers (e.g. `zaf-statssa-dts-2021-v1`), not numeric database IDs. The numeric IDs visible in URLs are internal only.

**Solution:** Updated the scraper to extract the `idno` string field from the catalog list response and use that for all subsequent API calls. Result: 313 → 596 studies successfully processed.

---

### Challenge 2: Free Downloads Hidden Behind HTML Page

**Problem:** First version of scraper reported `FAILED_NO_DOWNLOAD_LINK` for all 313 DataFirst studies because the JSON API `/resources` endpoint returned empty arrays.

**Root cause:** DataFirst separates microdata (login-required, in the API) from related materials (free PDFs, accessible only via HTML at `/related-materials`). The API does not expose the free files.

**Solution:** Added a secondary BeautifulSoup HTML scraper that visits each study's `/related-materials` HTML page, finds all `/download/` links, and downloads them. This resulted in 1,307 successfully downloaded files.

---

### Challenge 3: Harvard Murray Website Is Just a Landing Page

**Problem:** The Harvard Murray scraper found only 9 pages and downloaded only 1 file, despite the Murray Archive containing "over 100 terabytes of data."

**Root cause:** `www.murray.harvard.edu` is an institutional landing page. All actual datasets are stored on Harvard Dataverse at `dataverse.harvard.edu/dataverse/mra`, which is a completely separate URL.

**Solution:** Wrote a new `harvard_dataverse_scraper.py` that uses the Harvard Dataverse public REST API to search the `mra` subtree, retrieve dataset metadata, list files, and download public files. This increased Harvard projects from 9 to 922.

---

### Challenge 4: Mixed Status Values in Database

**Problem:** Two different status values existed in the FILES table — `SUCCESS` (from old scraper) and `SUCCEEDED` (from new scraper) — both meaning the same thing.

**Root cause:** The initial scraper used `SUCCESS` before the professor's enum was confirmed. The updated scraper correctly used `SUCCEEDED`.

**Solution:** Applied a normalization query after all scraping was complete:
```python
conn.execute("UPDATE FILES SET status='SUCCEEDED' WHERE status='SUCCESS'")
```
Result: 9,989 unified `SUCCEEDED` records.

---

### Challenge 5: Git Refusing to Commit the Database File

**Problem:** Running `git add 23079506-seeding.db` produced no error but the file was not staged, because `*.db` was in `.gitignore`.

**Root cause:** The `.gitignore` file contained `*.db` to prevent the working `metadata.db` from being committed. This also blocked the submission database.

**Solution:** Two-step fix:
1. Added `!23079506-seeding.db` to `.gitignore` to whitelist the specific file
2. Used `git add -f 23079506-seeding.db` to force-add it

---

### Challenge 6: Python SSL Warning on macOS

**Problem:** Every run displayed:
```
NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+,
currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'
```

**Root cause:** macOS ships with LibreSSL instead of OpenSSL. urllib3 v2 prefers OpenSSL but works with LibreSSL.

**Solution:** This warning is harmless — all downloads complete successfully. Suppressed in production by filtering warnings; no code changes required.

---

### Challenge 7: DataFirst API Uses idno String in URL, Not Numeric ID

**Problem:** When checking the catalog API response, studies return a numeric `id` (e.g. `940`) AND a string `idno` (e.g. `zaf-statssa-dts-2021-v1`). The related-materials HTML page uses the numeric ID in its URL (`/catalog/940/related-materials`) but the detail API uses the string idno.

**Root cause:** NADA software has two separate identifier systems — an internal database integer ID and a public string identifier.

**Solution:** The scraper extracts both: uses `idno` for API calls and `id` (numeric) for HTML page scraping.

---

### Challenge 8: Harvard Dataverse Restricted Files

**Problem:** 11,198 files on Harvard Dataverse returned HTTP 403 or were flagged as `restricted: true` in the API response.

**Root cause:** Murray Archive datasets require an application form and approval process. Restricted files cannot be downloaded without an account and approved access request.

**Solution:** The scraper checks the `restricted` field in the API file metadata before attempting download. Restricted files are immediately recorded as `FAILED_LOGIN_REQUIRED` without wasting a download attempt.

---

## 12. Submission Checklist

| Requirement | Status |
|-------------|--------|
| Scraper built for DataFirst UCT (repo #8) | ✅ |
| Scraper built for Harvard Murray Archive (repo #18) | ✅ |
| Multiple search queries used | ✅ |
| Full catalog crawl (not just keyword search) | ✅ |
| Files downloaded from both repos | ✅ 9,989 files |
| SQLite database with professor's exact schema | ✅ |
| All 6 tables populated | ✅ |
| Database named `23079506-seeding.db` | ✅ |
| Database in GitHub repository root | ✅ |
| `download_method` = `API-CALL` or `SCRAPING` | ✅ |
| Descriptive fail statuses (not just FAILED) | ✅ |
| License recorded per project | ✅ 1,518 records |
| Person/author roles recorded | ✅ 24,757 records |
| Keywords recorded where available | ✅ 1,727 records |
| Export to CSV | ✅ 6 CSV files |
| GitHub repo with `part-1-release` tag | ✅ |
| README with full documentation | ✅ |

---

## Requirements

```
requests
beautifulsoup4
lxml
tqdm
python-dotenv
```

**Python 3.9+ required.** Tested on macOS Ventura with Python 3.9.

---

## Links

- **GitHub Repository:** https://github.com/QNabila/Seeding-QDArchive-
- **Git Tag:** `part-1-release`
- **Database File:** `23079506-seeding.db` (in repository root)
- **Downloaded Data:** https://faubox.rrze.uni-erlangen.de/getlink/fi3AuAAgHVmFWQzG8rwAns/

---

## License

- **Code:** MIT License
- **Data:** Downloaded under respective source licenses
  - DataFirst UCT: CC BY (Creative Commons Attribution)
  - Harvard Dataverse: CC0 or as specified per dataset