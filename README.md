# Seeding QDArchive – Part 1: Data Acquisition

This project implements a small pipeline for collecting qualitative research datasets that may contain QDA files.

The script performs the following steps:

• queries repositories such as **Zenodo** and **DataverseNO** for candidate datasets  
• checks dataset files locally to detect known **QDA file extensions**  
• ignores datasets that do not provide license information  
• downloads the full dataset into a structured local directory  
• stores metadata for each detected QDA file in a **SQLite database**  
• exports the database content into **metadata.csv**

## Environment Setup

Create a virtual environment and install the required dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt