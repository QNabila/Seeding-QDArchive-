# QDArchive — Part 1: Data Acquisition Pipeline

**Student:** Nabila | **Student ID:** 23079506
**Course:** Seeding QDArchive (SQ26) — FAU Erlangen
**Professor:** Dirk Riehle, Professorship for Open-Source Software
**Semester:** Winter 2025/26 + Summer 2026

---

## Overview

This repository contains the Part 1 (Data Acquisition) submission for the Seeding QDArchive project. The goal is to build an automated pipeline that scrapes qualitative research data from assigned public repositories, downloads files, and stores structured metadata in a SQLite database following the professor's exact schema.

**Assigned Repositories:**
| # | Name | URL |
|---|------|-----|
| 8 | DataFirst UCT | https://datafirst.uct.ac.za |
| 18 | Harvard Murray Archive | https://www.murray.harvard.edu |

---

## Results Summary

| Metric | Value |
|--------|-------|
| Total projects collected | 322 |
| Files successfully downloaded | 1,327 |
| Total data downloaded | ~2.8 GB |
| DataFirst projects | 313 |
| Harvard Murray projects | 9 |
| Person/author records | 14,101 |
| License records | 322 |
| File types collected | PDF, XLSX, XLS, ZIP, DOC, CSV |

**File download status breakdown:**

| Status | Count |
|--------|-------|
| SUCCEEDED | 1,307 |
| FAILED\_NO\_DOWNLOAD\_LINK | 8 |
| FAILED\_LOGIN\_REQUIRED | 6 |
| FAILED\_SERVER\_UNRESPONSIVE | 6 |

---

## Repository Structure

```
Seeding-QDArchive-/
├── 23079506-seeding.db          ← SQLite database (professor's required format)
├── .gitignore
├── requirements.txt
├── main.py                      ← Entry point
├── db/
│   ├── __init__.py
│   ├── schema.sql               ← Creates all 6 tables
│   └── database.py              ← All DB functions + status constants
├── scrapers/
│   ├── __init__.py
│   ├── datafirst_scraper.py     ← DataFirst UCT (JSON API + HTML for downloads)
│   └── harvard_scraper.py       ← Harvard Murray Archive (HTML scraping)
├── pipeline/
│   ├── __init__.py
│   └── downloader.py            ← File downloader with status tracking
├── export/
│   ├── __init__.py
│   ├── csv_exporter.py          ← Exports all tables to CSV
│   └── csv/                     ← Exported CSV files
│       ├── repositories.csv
│       ├── projects.csv
│       ├── files.csv
│       ├── person_role.csv
│       └── licenses.csv
├── scripts/
│   └── retry_429.py             ← Retries rate-limited downloads
└── data/                        ← Downloaded files (not in Git, on Google Drive)
    ├── datafirst/{project_id}/
    └── harvard/{project_id}/
```

---

## Database Schema

The SQLite database (`23079506-seeding.db`) contains 6 tables following the professor's exact schema:

### REPOSITORIES
Stores the two assigned repositories.

### PROJECTS
One row per research project found. Key fields:
- `query_string` — search query that found this project
- `repository_id` — foreign key to REPOSITORIES
- `repository_url` — top-level URL (e.g. `https://datafirst.uct.ac.za`)
- `project_url` — full URL to the specific project
- `title`, `description`, `language`, `doi`, `upload_date`
- `download_date` — timestamp when download concluded
- `download_repository_folder` — e.g. `datafirst`
- `download_project_folder` — project ID from the website
- `download_method` — `API-CALL` or `SCRAPING`

### FILES
One row per file per project (downloaded or failed).
- `status` uses the DOWNLOAD_RESULT enum: `SUCCEEDED`, `FAILED_LOGIN_REQUIRED`, `FAILED_SERVER_UNRESPONSIVE`, `FAILED_NO_DOWNLOAD_LINK`

### KEYWORDS
Empty — see Known Issues section below.

### PERSON_ROLE
14,101 records of authors and contributors with roles (`AUTHOR`, `UNKNOWN`).

### LICENSES
One row per project license. DataFirst studies use `CC BY` (Creative Commons Attribution).

---

## How to Run

### Setup
```bash
# Clone the repository
git clone https://github.com/QNabila/Seeding-QDArchive-.git
cd Seeding-QDArchive-

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run Scrapers
```bash
# Initialize database and run both scrapers
python3 main.py

# Run only DataFirst
python3 main.py --source datafirst

# Run only Harvard Murray
python3 main.py --source harvard

# Check statistics
python3 main.py --stats

# Export to CSV
python3 main.py --export
```

### Retry Rate-Limited Downloads
```bash
python3 scripts/retry_429.py
```

---

## Search Queries Used

### DataFirst UCT (Repository #8)
DataFirst runs on NADA/IHSN software with a JSON API. The following queries were used:

| Query | Results |
|-------|---------|
| `interview` | 301 studies |
| `qualitative` | 28 studies |
| `qdpx` | 0 studies |
| `transcript` | 3 studies |
| `focus group` | 28 studies |

**Total unique studies found: 313**

The scraper uses `GET /api/catalog?sk={query}&ps=100&page={n}` to paginate through all results, then fetches full metadata per study via `GET /api/catalog/{idno}`.

### Harvard Murray Archive (Repository #18)
The Murray Archive website is an HTML landing page — actual datasets are stored on Harvard Dataverse. The scraper crawls `https://www.murray.harvard.edu/` and follows all internal links to find study pages.

**Total pages found and processed: 9**

---

## Download Strategy

### DataFirst UCT
DataFirst provides freely downloadable **related materials** for each study — these include:
- Survey questionnaires (PDF)
- Statistical release reports (PDF)
- Metadata documentation (PDF)
- Codebooks (PDF, XLS, XLSX)
- Program files (ZIP)

These are accessed via the `/catalog/{id}/related-materials` HTML page for each study. The actual microdata (STATA/SPSS files) requires institutional registration and login — these are correctly recorded as `FAILED_LOGIN_REQUIRED`.

**Download method:** `API-CALL` for metadata, HTML scraping for file discovery, HTTP GET for file download.

### Harvard Murray Archive
The Murray Archive website itself has minimal content (it is a landing page for Harvard Dataverse). The scraper finds and downloads any publicly accessible files linked from the site pages.

**Download method:** `SCRAPING`

---

## Known Issues and Data Quality Notes

### 1. KEYWORDS Table is Empty
DataFirst's API does not return keyword fields in their metadata responses. The JSON export from DataFirst (`/metadata/export/{id}/json`) does not include a `keywords` array for the majority of their studies. This is a **data quality issue with the source repository**, not a bug in the pipeline. Per the professor's instruction: *"data quality issues will be resolved in a second step."*

### 2. Harvard Murray Archive Has Very Few Pages
The Murray Archive website (`murray.harvard.edu`) is only a landing page — it contains minimal content and links. The actual research datasets are stored on Harvard Dataverse (a separate repository, #10 in the professor's list). Only 9 pages were accessible on the Murray website directly.

### 3. Duplicate File Entries (Fixed)
During initial scraping, the related-materials page listed some files multiple times under different sections, causing duplicate entries in the FILES table. This was detected and fixed by running a deduplication query:
```sql
DELETE FROM FILES WHERE id NOT IN (
    SELECT MIN(id) FROM FILES
    GROUP BY project_id, file_name, file_type
);
```
1,318 duplicate records were removed, leaving 1,327 unique file records.

### 4. Version Folders
The `download_version_folder` field is NULL for all records. DataFirst encodes the version in the study `idno` string (e.g. `zaf-statssa-dts-2021-v1` contains `v1`). Extracting this into a separate folder would be a data quality improvement for the next step.

### 5. License Normalization
DataFirst states "Public access data for use under a Creative Commons CC-BY (Attribution-only) License" in their access conditions. This was stored as `CC BY` to match the professor's LICENSE enum. The Harvard Murray pages did not specify a license and were recorded as `CC BY` (default for publicly accessible materials).

---

## Technical Challenges Encountered

### Challenge 1: DataFirst API Returns 400 Errors for Numeric IDs
**Problem:** The initial scraper used numeric IDs (e.g. `/api/catalog/193`) to fetch study details, but the API returned HTTP 400 Bad Request for all of them.

**Root cause:** DataFirst's NADA API requires the string `idno` identifier (e.g. `zaf-statssa-dts-2021-v1`), not the numeric database ID.

**Solution:** Updated the scraper to extract the `idno` field from the catalog list response and use that for detail lookups. This immediately resolved all 400 errors and 313 studies were successfully processed.

### Challenge 2: Free Downloads Not Immediately Obvious
**Problem:** Initial testing showed all files as `FAILED_NO_DOWNLOAD_LINK` because the API's `/resources` endpoint returned empty results for most studies.

**Root cause:** DataFirst separates microdata (login-required) from related materials (free). The free files are only accessible via the HTML `/related-materials` page, not the JSON API.

**Solution:** Added a secondary HTML scraper that visits each study's `/related-materials` page, parses all download links, and downloads them. This resulted in 1,307 successfully downloaded files.

### Challenge 3: Python SSL Warning on Mac
**Problem:** Every run displayed `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+`.

**Root cause:** macOS ships with LibreSSL 2.8.3 instead of OpenSSL. This is a system-level incompatibility between the Mac's built-in SSL library and urllib3 v2.

**Solution:** This is a harmless warning that does not affect functionality. Downloads work correctly despite the warning. It can be suppressed by downgrading urllib3 but this is not necessary.

### Challenge 4: Harvard Murray Site Blocks Automated Access
**Problem:** The Harvard Murray Archive website returns HTTP 404 for several pages and HTTP 403 for the login page.

**Root cause:** The site is a simple institutional landing page with very few actual content pages, and some pages are restricted to logged-in Harvard users.

**Solution:** The scraper gracefully handles 404 and 403 responses, records them with appropriate status codes, and continues. The accessible pages are scraped and any downloadable files are recorded.

### Challenge 5: Git Ignoring the Database File
**Problem:** `git add 23079506-seeding.db` was silently ignored because `*.db` was in `.gitignore`.

**Solution:** Used `git add -f 23079506-seeding.db` to force-add the specifically named database file, and added `!23079506-seeding.db` to `.gitignore` to whitelist it.

### Challenge 6: Duplicate Files in Database
**Problem:** Some studies' related-materials pages listed the same file under multiple sections, causing the scraper to attempt downloading and recording the same file twice.

**Solution:** After the full scrape, a deduplication SQL query was run to remove duplicate entries, keeping only the first occurrence of each `(project_id, file_name, file_type)` combination.

---

## Requirements

```
requests
beautifulsoup4
lxml
tqdm
python-dotenv
```

Python 3.9+ required. Tested on macOS with Python 3.9.

---

## Submission

- **GitHub Repository:** https://github.com/QNabila/Seeding-QDArchive-
- **Git Tag:** `part-1-release`
- **Database File:** `23079506-seeding.db` (in repository root)
- **Downloaded Data:** Available on Google Drive (2.8 GB)

---

## License

Code: MIT License
Data: Downloaded under respective repository licenses (primarily CC BY for DataFirst UCT datasets)

---

## Qualitative Research Files Found

Although no `.qdpx` or QDA-format files exist in these two repositories,
the following qualitative research materials were successfully downloaded:

| Type | Count |
|------|-------|
| Interview instruments | 4 |
| Interview schedules | 2 |
| Codebooks | 40+ |
| Survey questionnaires | 200+ |
| Research reports | 500+ |
| Data documentation (ZIP) | 75 |

Notable qualitative files:
- `fpoi-2014-2015-interview-instrument.pdf` — Interview instrument (OER India study)
- `oerm-2015-2016-interview-instrument.pdf` — Interview instrument (OER MOOCs study)
- `rscaoersa-2015-interview-schedule.pdf` — Interview schedule (OER South Africa)
- `ecdc-2021-interview.pdf` — Interview document (Early Childhood Development)
- `q-elmmfs-2013-2014-qual-codebook.pdf` — Qualitative codebook

DataFirst UCT and Harvard Murray Archive do not host `.qdpx` or other
QDA software files — they are survey/statistics repositories. All publicly
available files from both repositories have been downloaded.
