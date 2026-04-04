"""
Retry Script for Rate-Limited (HTTP 429) Downloads
----------------------------------------------------
Run this script after the main pipeline to retry any files
that failed with FAILED_HTTP_429.

Usage:
    python3 scripts/retry_429.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import get_connection, insert_file, STATUS_SUCCESS
from pipeline.downloader import download_file, HEADERS

DATA_ROOT = Path(__file__).parent.parent / "data"


def get_failed_files(status="FAILED_HTTP_429"):
    """Get all files with a specific failed status."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            f.id, f.file_name, f.file_type,
            p.download_repository_folder,
            p.download_project_folder,
            p.project_url,
            p.id as project_id
        FROM FILES f
        JOIN PROJECTS p ON f.project_id = p.id
        WHERE f.status = ?
    """, (status,)).fetchall()
    conn.close()
    return rows


def update_file_status(file_id, new_status):
    """Update a file's status in the DB."""
    conn = get_connection()
    conn.execute("UPDATE FILES SET status = ? WHERE id = ?", (new_status, file_id))
    conn.commit()
    conn.close()


def retry_files(status="FAILED_HTTP_429", delay=5):
    """Retry all files with the given status."""
    files = get_failed_files(status)
    print(f"Found {len(files)} files with status '{status}'")

    if not files:
        print("Nothing to retry.")
        return

    for f in files:
        repo_folder = f["download_repository_folder"]
        proj_folder = f["download_project_folder"]
        file_name = f["file_name"]
        file_id = f["id"]

        # Reconstruct the download URL (best effort)
        project_url = f["project_url"]
        file_url = f"{project_url}/{file_name}"

        dest_path = DATA_ROOT / repo_folder / proj_folder / file_name

        print(f"\n  Retrying: {file_name}")
        print(f"  URL: {file_url}")
        print(f"  Waiting {delay}s before download...")
        time.sleep(delay)

        new_status = download_file(file_url, dest_path)
        update_file_status(file_id, new_status)
        print(f"  Result: {new_status}")


if __name__ == "__main__":
    retry_files("FAILED_HTTP_429", delay=5)
