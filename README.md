# QDArchive — Seeding Project (Part 1 + Part 2)

**Student:** Nabila Kader | **Student ID:** 23079506
**Course:** Seeding QDArchive (SQ26) — Applied Software Engineering
**University:** FAU Erlangen-Nürnberg
**Professor:** Prof. Dr. Dirk Riehle, Professorship for Open-Source Software
**Semester:** Winter 2025/26 + Summer 2026
**Submission Tags:** `part-1-release` · `classification-results`

---

## Table of Contents

**Part 1 — Data Acquisition**
1. [Project Overview](#1-project-overview)
2. [Assigned Repositories](#2-assigned-repositories)
3. [Part 1 Results](#3-part-1-results)
4. [Repository Structure](#4-repository-structure)
5. [Database Schema](#5-database-schema)
6. [How to Run Part 1](#6-how-to-run-part-1)
7. [Scraping Strategy](#7-scraping-strategy)
8. [Search Queries Used](#8-search-queries-used)
9. [Download Strategy](#9-download-strategy)
10. [Data Quality Notes](#10-data-quality-notes)
11. [Technical Challenges (Part 1)](#11-technical-challenges-part-1)

**Part 2 — Data Classification**

12. [Part 2 Overview](#12-part-2-overview)
13. [Part 2 Results](#13-part-2-results)
14. [Classification Methodology](#14-classification-methodology)
15. [ISIC Results by Repository](#15-isic-results-by-repository)
16. [How to Run Part 2](#16-how-to-run-part-2)
17. [Technical Challenges (Part 2)](#17-technical-challenges-part-2)
18. [Submission Checklist](#18-submission-checklist)

---

## 1. Project Overview

QDArchive is a web service for researchers to publish and archive qualitative data, with an emphasis on Qualitative Data Analysis (QDA) files. This project seeds QDArchive in two phases:

**Part 1 — Data Acquisition:** Build an automated pipeline that scrapes qualitative research projects from assigned public repositories, downloads all publicly available files, and stores structured metadata in a SQLite database.

**Part 2 — Data Classification:** Classify every collected project by project type (QDA/QD/OTHER/NOT_A_PROJECT) and by economic sector using the ISIC Rev. 5 international standard (down to division level).

---

## 2. Assigned Repositories

| # | Name | URL | Type |
|---|------|-----|------|
| 8 | DataFirst UCT | https://datafirst.uct.ac.za | JSON API + HTML |
| 18 | Harvard Murray Archive | https://www.murray.harvard.edu | HTML + Harvard Dataverse API |

---

## 3. Part 1 Results

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
| `FAILED_SERVER_UNRESPONSIVE` | 44 | Server unresponsive, HTTP error, or timeout |

### Grading Script Result
```
Summary: 10 passed, 1 warnings, 0 errors
```
The only warning is the extra REPOSITORIES table — intentional for foreign key references.

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
├── 23079506-seeding.db                  ← Part 1: SQLite acquisition database
├── 23079506-sq26-classification.db      ← Part 2: SQLite classification database
├── 23079506-classification.xlsx         ← Part 2: XLSX export (required submission)
├── 23079506-classification-report.pdf   ← Part 2: PDF report (vector graphics)
├── 23079506-classification-report.docx  ← Part 2: Word version (editable)
├── README.md                            ← This file
├── .gitignore
├── requirements.txt
├── main.py                              ← Part 1 main entry point
│
├── db/
│   ├── schema.sql                       ← Creates all 6 tables + seeds repositories
│   └── database.py                      ← DB functions, status/role constants
│
├── scrapers/
│   ├── datafirst_scraper.py             ← DataFirst UCT keyword search scraper
│   └── harvard_scraper.py               ← Harvard Murray website HTML scraper
│
├── pipeline/
│   └── downloader.py                    ← HTTP file downloader with status tracking
│
├── export/
│   ├── csv_exporter.py                  ← Exports all 6 tables to CSV
│   └── csv/                             ← 6 CSV exports (repositories, projects, files…)
│
├── scripts/
│   ├── classify.py                      ← Part 2: ISIC classifier (keyword-based)
│   ├── generate_report.py               ← Part 2: PDF report generator (vector charts)
│   ├── generate_word.py                 ← Part 2: Word report generator
│   ├── crawl_all_datafirst.py           ← Full DataFirst catalog crawl
│   ├── harvard_dataverse_scraper.py     ← Harvard Dataverse API scraper
│   └── retry_429.py                     ← Retries HTTP 429 rate-limited downloads
│
└── data/                                ← NOT in Git — on Google Drive (link below)
    ├── datafirst/{project_idno}/
    └── harvard/{doi_as_folder}/
```

---

## 5. Database Schema

### Part 1 Database: `23079506-seeding.db`

Six tables following the professor's exact schema:

| Table | Rows | Description |
|-------|------|-------------|
| REPOSITORIES | 2 | DataFirst + Harvard |
| PROJECTS | 1,518 | One row per research project |
| FILES | 21,232 | All files (downloaded + failed) |
| KEYWORDS | 1,727 | Keywords per project |
| PERSON_ROLE | 24,757 | Authors, uploaders, contributors |
| LICENSES | 1,518 | License per project |

**PROJECTS key fields:**

| Field | Type | Notes |
|-------|------|-------|
| repository_id | INTEGER | FK → REPOSITORIES |
| project_url | URL | Full URL to project page |
| title | STRING | Project title |
| description | TEXT | Abstract / description |
| doi | URL | DOI URL if available |
| download_method | ENUM | `API-CALL` or `SCRAPING` |
| download_repository_folder | STRING | e.g. `datafirst` |
| download_project_folder | STRING | Project ID from source site |

**DOWNLOAD_RESULT enum values:**
- `SUCCEEDED` — file downloaded successfully
- `FAILED_LOGIN_REQUIRED` — institutional registration required
- `FAILED_SERVER_UNRESPONSIVE` — server did not respond
- `FAILED_NO_DOWNLOAD_LINK` — no downloadable file found
- `FAILED_HTTP_ERROR` — other HTTP error
- `FAILED_TIMEOUT` — request timed out

### Part 2 Database: `23079506-sq26-classification.db`

Extends the Part 1 schema with two additional columns on PROJECTS:

| Column | Type | Description |
|--------|------|-------------|
| `type` | TEXT | `QDA_PROJECT`, `QD_PROJECT`, `OTHER_PROJECT`, or `NOT_A_PROJECT` |
| `primary_class` | TEXT | ISIC Rev. 5 division e.g. `86: Human health activities` |
| `secondary_class` | TEXT | Second ISIC division if applicable |

---

## 6. How to Run Part 1

### Prerequisites
- Python 3.9+
- macOS / Linux
- Internet connection

### Setup
```bash
git clone https://github.com/QNabila/Seeding-QDArchive-.git
cd Seeding-QDArchive-
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the Pipeline
```bash
python3 main.py                          # Full pipeline (both repos + export)
python3 main.py --source datafirst       # DataFirst only
python3 main.py --source harvard         # Harvard only
python3 main.py --stats                  # Print DB statistics
python3 main.py --export                 # Export to CSV only

python3 scripts/crawl_all_datafirst.py           # Full catalog crawl (596 studies)
python3 scripts/harvard_dataverse_scraper.py     # Harvard Dataverse API
python3 scripts/retry_429.py                     # Retry rate-limited downloads
```

### Expected Runtime

| Script | Time |
|--------|------|
| `main.py --source datafirst` | ~18 minutes |
| `crawl_all_datafirst.py` | ~45–60 minutes |
| `harvard_dataverse_scraper.py` | ~20–30 minutes |

---

## 7. Scraping Strategy

**Approach 1 — Query-based search:** Used for `main.py` with DataFirst. Searches using specific queries (`interview`, `qualitative`, `qdpx`, etc.) via the NADA JSON API.

**Approach 2 — Full catalog crawl:** Used for `crawl_all_datafirst.py`. Fetches all 596 studies using pagination (`ps=100&page=N`), no keyword filter.

**Approach 3 — REST API:** Used for `harvard_dataverse_scraper.py`. Uses the Harvard Dataverse public REST API to search the `mra` subtree, list files, and download public content.

---

## 8. Search Queries Used

### DataFirst UCT

| Query | Studies Found |
|-------|--------------|
| `interview` | 301 |
| `qualitative` | 28 |
| `focus group` | 28 |
| `transcript` | 3 |
| `qdpx` | 0 |
| *(full catalog crawl)* | 596 total |

### Harvard Dataverse (Murray Archive)

| Query | Subtree |
|-------|---------|
| `interview` | `mra` |
| `qualitative` | `mra` |
| `longitudinal` | `mra` |
| `oral history` | `mra` |
| `survey` | `mra` |
| `interview transcript qualitative data` | `harvard` |

---

## 9. Download Strategy

### DataFirst UCT
- **Metadata:** Free via NADA JSON API (`/api/catalog/{idno}`)
- **Related materials:** Free PDFs/ZIPs via HTML scraping of `/related-materials` page
- **Microdata:** Login required — recorded as `FAILED_LOGIN_REQUIRED`

### Harvard Murray Archive / Dataverse
- **Metadata + file lists:** Harvard Dataverse REST API (`/api/search`, `/api/datasets/:persistentId/versions/:version/files`)
- **Public files:** Downloaded via `/api/access/datafile/{id}`
- **Restricted files:** `restricted: true` in API → recorded as `FAILED_LOGIN_REQUIRED` without wasting a request

---

## 10. Data Quality Notes

**Issue 1 — Keywords missing for DataFirst:** The NADA API does not include keyword fields for most studies. Keywords are populated only for Harvard Dataverse datasets.

**Issue 2 — Harvard Murray website is a landing page:** `murray.harvard.edu` has only ~9 pages. All actual data is on `dataverse.harvard.edu/dataverse/mra`.

**Issue 3 — Duplicate file entries (fixed):** Some DataFirst related-materials pages listed the same file multiple times. 1,318 duplicates removed via deduplication SQL.

**Issue 4 — `download_version_folder` is NULL:** DataFirst encodes version in the `idno` string. Explicit subfolders are a future improvement.

**Issue 5 — Status enum normalized:** Initial scraper used `SUCCESS`; corrected to `SUCCEEDED` via `UPDATE FILES SET status='SUCCEEDED' WHERE status='SUCCESS'`.

**Issue 6 — License values:** DataFirst → `CC BY`. Harvard Dataverse → `CC0` or as specified per dataset.

---

## 11. Technical Challenges (Part 1)

### Challenge 1: DataFirst API Returns HTTP 400 for Numeric IDs
DataFirst's NADA API uses string `idno` identifiers (e.g. `zaf-statssa-dts-2021-v1`), not numeric IDs. Updated scraper to use `idno` strings. Result: 313 → 596 studies processed.

### Challenge 2: Free Downloads Hidden Behind HTML Page
`/resources` API endpoint returned empty arrays. Free PDFs are on the HTML `/related-materials` page only. Added BeautifulSoup scraper for that page. Result: 1,307 files downloaded.

### Challenge 3: Harvard Murray Website Is a Landing Page
`www.murray.harvard.edu` had only 9 pages and 1 file. Wrote a new `harvard_dataverse_scraper.py` using the Dataverse REST API. Result: 9 → 922 projects.

### Challenge 4: Mixed Status Values
Both `SUCCESS` and `SUCCEEDED` existed in FILES. Applied normalization query: 9,989 unified `SUCCEEDED` records.

### Challenge 5: Git Ignoring the DB File
`*.db` in `.gitignore` blocked the submission database. Fixed with `!23079506-seeding.db` whitelist entry + `git add -f`.

### Challenge 6: Harvard Dataverse Restricted Files
11,198 files flagged `restricted: true` in API metadata. Scraper checks `restricted` field before attempting download and records these as `FAILED_LOGIN_REQUIRED` immediately.

---

## 12. Part 2 Overview

Part 2 classifies the 1,518 collected projects using two taxonomies:

1. **Project type** — based on file extensions present in the project
2. **ISIC Rev. 5 classification** — economic sector at division (two-digit) level, assigned using keyword-based analysis of titles, descriptions, and metadata

Deliverables:
- `23079506-sq26-classification.db` — SQLite database with `type`, `primary_class`, `secondary_class` columns
- `23079506-classification.xlsx` — XLSX export with 6 required columns
- `23079506-classification-report.pdf` — PDF report with vector charts and Table of Contents
- `23079506-classification-report.docx` — Editable Word version

---

## 13. Part 2 Results

### Project Type Classification

| Type | Criterion | Count |
|------|-----------|-------|
| `QDA_PROJECT` | Contains a QDA file (.qdpx, .nvp, .atlproj, etc.) | **3** |
| `QD_PROJECT` | Has primary data files (PDF, DOCX, TXT, etc.) | **1,339** |
| `OTHER_PROJECT` | Has files but not primary data files | **76** |
| `NOT_A_PROJECT` | No usable files identified | **100** |
| **Total** | | **1,518** |

### ISIC Classification — Top 5 Overall

| Rank | ISIC | Division | Count | % |
|------|------|----------|-------|---|
| 1 | 86 | Human health activities | 430 | 28.3% |
| 2 | 72 | Scientific research and development | 287 | 18.9% |
| 3 | 64 | Financial service activities | 198 | 13.0% |
| 4 | 85 | Education | 175 | 11.5% |
| 5 | 78 | Employment activities | 132 | 8.7% |

### By Repository

| Repository | Total | QDA | QD | Other | Not | Dominant ISIC Class |
|------------|-------|-----|-----|-------|-----|---------------------|
| DataFirst UCT | 596 | 0 | 568 | 0 | 28 | 72 — Scientific R&D (151) |
| Harvard Dataverse | 922 | 3 | 771 | 76 | 72 | 86 — Human health (403) |

### Key Findings

- **3 QDA_PROJECT files found** — all in Harvard Dataverse. DataFirst contains no QDA files, confirming it is a quantitative statistics repository.
- **Human Health Activities (ISIC 86)** dominates overall (28.3%), driven by the Murray Archive's focus on health psychology research.
- **Scientific Research (ISIC 72)** dominates DataFirst (151 projects) due to broad survey study titles.
- Classification accuracy: ~85% confirmed by manual spot-check of a random sample.

---

## 14. Classification Methodology

### Step 1 — Project Type

Rules applied in priority order to each project's file extensions:

```
QDA_PROJECT   → contains .qdpx, .nvp, .nvpx, .atlproj, .qda, .mx24, .mx12, .f4, .maxqda
QD_PROJECT    → no QDA file, but has .pdf, .doc, .docx, .txt, .rtf, .odt
OTHER_PROJECT → has files but none of the above types
NOT_A_PROJECT → no files at all (or only failed/restricted downloads)
```

### Step 2 — ISIC Rev. 5 Division Classification

Implemented in `scripts/classify.py` using 14 keyword rule sets covering:

| Rule Set | ISIC | Example Keywords |
|----------|------|-----------------|
| Health | 86 | health, medical, clinical, HIV, disease, patient |
| Education | 85 | education, school, learning, teaching, student |
| Finance | 64 | finance, bank, credit, microfinance, insurance |
| Employment | 78 | employment, labour, work, job, unemployment |
| Government | 84 | government, policy, public administration, governance |
| Research | 72 | survey, research, study, data collection |
| Agriculture | 01 | agriculture, farming, crop, livestock |
| Tourism | 55 | tourism, travel, hospitality, accommodation |
| Utilities | 35 | energy, electricity, water, utility |
| Social work | 88 | social work, welfare, community support |
| Market research | 73 | market, consumer, advertising, brand |
| Admin support | 82 | administrative, business support, consulting |

Classification inputs: project title + description + keywords (concatenated, lowercased, matched against rule sets).

---

## 15. ISIC Results by Repository

### DataFirst UCT (596 projects)

| Rank | ISIC | Division | Count |
|------|------|----------|-------|
| 1 | 72 | Scientific research and development | 151 |
| 2 | 78 | Employment activities | 115 |
| 3 | 84 | Public administration and defence | 103 |
| 4 | 73 | Advertising and market research | 61 |
| 5 | 64 | Financial service activities | 52 |
| 6 | 85 | Education | 49 |
| 7 | 86 | Human health activities | 27 |

*DataFirst focuses on South African national surveys. The dominance of ISIC 72 (Research) reflects broad survey titles lacking specific health/education keywords.*

### Harvard Murray Archive / Dataverse (922 projects)

| Rank | ISIC | Division | Count |
|------|------|----------|-------|
| 1 | 86 | Human health activities | 403 |
| 2 | 64 | Financial service activities | 146 |
| 3 | 72 | Scientific research and development | 136 |
| 4 | 85 | Education | 126 |
| 5 | 73 | Advertising and market research | 30 |
| 6 | 01 | Crop and animal production | 29 |

*The Murray Archive's long-term focus on human development and psychology explains the dominance of ISIC 86.*

---

## 16. How to Run Part 2

### Classify Projects
```bash
# Classify all projects — writes type, primary_class, secondary_class
python3 scripts/classify.py
```

### Generate Reports
```bash
# PDF report with vector charts (requires reportlab)
python3 scripts/generate_report.py

# Word (.docx) report (requires python-docx + matplotlib)
python3 scripts/generate_word.py
```

### Dependencies (Part 2 only)
```bash
pip install reportlab python-docx matplotlib openpyxl
```

### Export XLSX
```bash
# The XLSX is already committed as 23079506-classification.xlsx
# To regenerate from the DB:
python3 -c "
import sqlite3, openpyxl
conn = sqlite3.connect('23079506-sq26-classification.db')
wb = openpyxl.Workbook()
ws = wb.active
ws.append(['repository_id','project_type','project_title','primary_class','secondary_class','no_project_files'])
for row in conn.execute('''
    SELECT p.repository_id, p.type, p.title, p.primary_class, p.secondary_class,
           COUNT(f.id)
    FROM PROJECTS p LEFT JOIN FILES f ON f.project_id=p.id
    GROUP BY p.id
'''):
    ws.append(list(row))
wb.save('23079506-classification.xlsx')
"
```

---

## 17. Technical Challenges (Part 2)

### Challenge 1: DataFirst Metadata Sparsity
Most DataFirst projects in the API return only a title and no description or keywords. This forced the classifier to operate on titles alone (~5–10 words), reducing accuracy for those 596 projects. Workaround: expanded keyword rule sets to catch single-word matches in titles.

### Challenge 2: Overlapping ISIC Categories
Many projects match multiple ISIC divisions. A health survey conducted by a government agency matches both ISIC 86 (health) and ISIC 84 (government). Resolution: primary match wins; the highest-scoring rule set determines `primary_class`, second-highest goes to `secondary_class`.

### Challenge 3: Vector Graphics Without Cairo
The assignment requires vector graphics in the PDF. The initial approach (matplotlib → SVG → svglib) failed because `svglib` requires `pycairo` which is not available without system-level Cairo libraries on macOS. Solution: rewrote all charts using **ReportLab's native drawing API** (`Drawing`, `HorizontalBarChart`, `Pie` from `reportlab.graphics`) — true vector output with no external dependencies.

### Challenge 4: Blank Page in PDF
The original PDF had a blank page 2 caused by a double `PageBreak` after the cover (`NextPageTemplate('normal')` followed by `PageBreak()` both triggered a page break). Fixed by removing the redundant `PageBreak()`.

---

## 18. Submission Checklist

### Part 1

| Requirement | Status |
|-------------|--------|
| Scraper for DataFirst UCT (repo #8) | ✅ |
| Scraper for Harvard Murray Archive (repo #18) | ✅ |
| Multiple search queries used | ✅ |
| Full catalog crawl (not just keyword search) | ✅ |
| Files downloaded from both repos | ✅ 9,989 files |
| SQLite database with professor's exact schema | ✅ |
| All 6 tables populated | ✅ |
| Database named `23079506-seeding.db` | ✅ |
| `download_method` = `API-CALL` or `SCRAPING` | ✅ |
| Descriptive fail statuses (not just FAILED) | ✅ |
| License recorded per project | ✅ 1,518 records |
| Person/author roles recorded | ✅ 24,757 records |
| Keywords recorded where available | ✅ 1,727 records |
| Export to CSV (6 files) | ✅ |
| Tagged `part-1-release` | ✅ |

### Part 2

| Requirement | Status |
|-------------|--------|
| `type` column set for all 1,518 projects | ✅ |
| ISIC Rev. 5 classification at division level | ✅ |
| `primary_class` set for all 1,518 projects | ✅ 100% coverage |
| `secondary_class` set where applicable | ✅ |
| DB committed as `23079506-sq26-classification.db` | ✅ |
| Tagged `classification-results` | ✅ |
| XLSX with all 6 required columns, 1,518 rows | ✅ |
| XLSX uploaded to moo.uni1.de | ✅ |
| Google Form submitted (×2, once per repo) | ✅ |
| PDF report with vector histograms + top-20 tables | ✅ |
| PDF uses vector graphics (zoomable) | ✅ Native ReportLab drawing |
| PDF has Table of Contents | ✅ |
| Comments on findings per repository | ✅ |
| No blank pages in PDF | ✅ Fixed |

---

## Links

- **GitHub Repository:** https://github.com/QNabila/Seeding-QDArchive-
- **Part 1 tag:** `part-1-release`
- **Part 2 tag:** `classification-results`
- **Part 1 database:** `23079506-seeding.db`
- **Part 2 database:** `23079506-sq26-classification.db`
- **Part 2 XLSX:** `23079506-classification.xlsx`
- **Part 2 PDF report:** `23079506-classification-report.pdf`
- **Downloaded data (Google Drive):** https://faubox.rrze.uni-erlangen.de/getlink/fi3AuAAgHVmFWQzG8rwAns/

---

## License

- **Code:** MIT License
- **Data:** Downloaded under respective source licenses
  - DataFirst UCT: CC BY (Creative Commons Attribution)
  - Harvard Dataverse: CC0 or as specified per dataset
