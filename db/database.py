import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "metadata.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Status constants
STATUS_SUCCESS = "SUCCESS"
STATUS_LOGIN_REQUIRED = "FAILED_LOGIN_REQUIRED"
STATUS_HTTP_404 = "FAILED_HTTP_404"
STATUS_HTTP_ERROR = "FAILED_HTTP_ERROR"
STATUS_NO_DOWNLOAD_LINK = "FAILED_NO_DOWNLOAD_LINK"
STATUS_TIMEOUT = "FAILED_TIMEOUT"
STATUS_UNKNOWN = "FAILED_UNKNOWN"

# Role constants
ROLE_AUTHOR = "AUTHOR"
ROLE_UPLOADER = "UPLOADER"
ROLE_OWNER = "OWNER"
ROLE_CONTRIBUTOR = "CONTRIBUTOR"
ROLE_UNKNOWN = "UNKNOWN"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("  Database initialized.")


def project_exists(project_url):
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM PROJECTS WHERE project_url = ?", (project_url,)
    ).fetchone()
    conn.close()
    return row is not None


def insert_project(data):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO PROJECTS (
            query_string, repository_id, repository_url, project_url,
            version, title, description, language, doi,
            upload_date, download_date,
            download_repository_folder, download_project_folder,
            download_version_folder, download_method
        ) VALUES (
            :query_string, :repository_id, :repository_url, :project_url,
            :version, :title, :description, :language, :doi,
            :upload_date, :download_date,
            :download_repository_folder, :download_project_folder,
            :download_version_folder, :download_method
        )
    """, data)
    project_id = cur.lastrowid
    conn.commit()
    conn.close()
    return project_id


def insert_file(project_id, file_name, file_type, status):
    conn = get_connection()
    conn.execute(
        "INSERT INTO FILES (project_id, file_name, file_type, status) VALUES (?,?,?,?)",
        (project_id, file_name, file_type or "", status)
    )
    conn.commit()
    conn.close()


def insert_keyword(project_id, keyword):
    conn = get_connection()
    conn.execute(
        "INSERT INTO KEYWORDS (project_id, keyword) VALUES (?,?)",
        (project_id, keyword.strip())
    )
    conn.commit()
    conn.close()


def insert_person(project_id, name, role=ROLE_UNKNOWN):
    conn = get_connection()
    conn.execute(
        "INSERT INTO PERSON_ROLE (project_id, name, role) VALUES (?,?,?)",
        (project_id, name.strip(), role)
    )
    conn.commit()
    conn.close()


def insert_license(project_id, license_str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO LICENSES (project_id, license) VALUES (?,?)",
        (project_id, license_str.strip())
    )
    conn.commit()
    conn.close()


def get_project_count():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM PROJECTS").fetchone()[0]
    conn.close()
    return count


def get_file_status_summary():
    conn = get_connection()
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM FILES GROUP BY status"
    ).fetchall()
    conn.close()
    return {row["status"]: row["cnt"] for row in rows}
