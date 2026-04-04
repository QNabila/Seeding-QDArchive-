CREATE TABLE IF NOT EXISTS REPOSITORIES (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS PROJECTS (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_string TEXT,
    repository_id INTEGER NOT NULL,
    repository_url TEXT NOT NULL,
    project_url TEXT NOT NULL,
    version TEXT,
    title TEXT NOT NULL,
    description TEXT,
    language TEXT,
    doi TEXT,
    upload_date TEXT,
    download_date TIMESTAMP NOT NULL,
    download_repository_folder TEXT NOT NULL,
    download_project_folder TEXT NOT NULL,
    download_version_folder TEXT,
    download_method TEXT NOT NULL CHECK(download_method IN ('SCRAPING','API-CALL')),
    FOREIGN KEY (repository_id) REFERENCES REPOSITORIES(id)
);

CREATE TABLE IF NOT EXISTS FILES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

CREATE TABLE IF NOT EXISTS KEYWORDS (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

CREATE TABLE IF NOT EXISTS PERSON_ROLE (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('AUTHOR','UPLOADER','OWNER','CONTRIBUTOR','UNKNOWN')),
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

CREATE TABLE IF NOT EXISTS LICENSES (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    license TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES PROJECTS(id)
);

INSERT OR IGNORE INTO REPOSITORIES (id, name, url) VALUES
    (1, 'datafirst', 'https://datafirst.uct.ac.za'),
    (2, 'harvard', 'https://www.murray.harvard.edu');
