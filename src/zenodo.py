from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from src.download_policy import DownloadPolicy, select_files
from src.util import ensure_dir, is_qda_file, safe_slug, try_download_file

ZENODO_API = "https://zenodo.org/api/records"


def _normalize_ext_terms(qda_exts: List[str], cap: int = 15) -> List[str]:
    terms: List[str] = []
    seen = set()
    for ext in qda_exts:
        t = (ext or "").lower().lstrip(".").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        terms.append(t)
        if len(terms) >= cap:
            break
    return terms


def _broad_query(qda_exts: List[str]) -> str:
    ext_terms = _normalize_ext_terms(qda_exts, cap=15)
    ext_part = "(" + " OR ".join(ext_terms) + ")"
    qual_part = '(qualitative OR interview OR transcript OR "focus group" OR ethnograph OR coding)'
    return f"({ext_part}) AND {qual_part}"


def search_records_overfetch(
    *,
    qda_exts: List[str],
    session: requests.Session,
    timeout: int,
    user_agent: str,
    overfetch: int,
) -> List[Dict]:
    query = _broad_query(qda_exts)
    headers = {"User-Agent": user_agent}

    gathered: List[Dict] = []
    page = 1
    size = 25
    max_pages = 200

    while len(gathered) < overfetch and page <= max_pages:
        resp = session.get(
            ZENODO_API,
            params={"q": query, "page": page, "size": size},
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()

        hits = ((payload.get("hits") or {}).get("hits") or [])
        if not hits:
            break

        gathered.extend(hits)
        page += 1

    return gathered[:overfetch]


def extract_license(record: Dict) -> Optional[str]:
    md = record.get("metadata") or {}
    lic = md.get("license")

    if isinstance(lic, dict):
        return lic.get("id") or lic.get("title")
    if isinstance(lic, str) and lic.strip():
        return lic.strip()
    return None


def extract_uploader(record: Dict) -> Tuple[Optional[str], Optional[str]]:
    md = record.get("metadata") or {}
    creators = md.get("creators") or []

    if isinstance(creators, list) and creators:
        first = creators[0] or {}
        if isinstance(first, dict):
            return first.get("name"), None

    return None, None


def record_has_qda_file(record: Dict, qda_exts: List[str]) -> bool:
    for f in (record.get("files") or []):
        key = (f or {}).get("key")
        if key and is_qda_file(key, qda_exts):
            return True
    return False


def _file_candidates_from_record(record: Dict) -> List[Dict]:
    files = record.get("files") or []
    candidates: List[Dict] = []

    for item in files:
        item = item or {}
        name = item.get("key")
        links = item.get("links") or {}
        url = links.get("self") or links.get("download")
        if not name or not url:
            continue

        raw_size = item.get("size")
        size_bytes = raw_size if isinstance(raw_size, int) else None

        candidates.append({"name": name, "url": url, "size_bytes": size_bytes})

    return candidates


def download_record(
    *,
    record: Dict,
    downloads_root: Path,
    qda_exts: List[str],
    session: requests.Session,
    connect_timeout: int,
    read_timeout: int,
    user_agent: str,
    policy: DownloadPolicy,
    run_budget_left_bytes: int,
) -> Tuple[str, List[Tuple[str, str]], int]:
    rec_id = str(record.get("id") or "unknown")
    md = record.get("metadata") or {}
    title = md.get("title") or f"zenodo-{rec_id}"

    slug = safe_slug(title)
    local_dir_rel = f"zenodo/{slug}-{rec_id}"
    local_dir = downloads_root / local_dir_rel
    ensure_dir(local_dir)

    (local_dir / "metadata.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    candidates = _file_candidates_from_record(record)
    selected = select_files(candidates, policy)

    qda_rows: List[Tuple[str, str]] = []
    bytes_used_run = 0
    bytes_used_dataset = 0

    for f in selected:
        name = f["name"]
        url = f["url"]
        size_bytes = f.get("size_bytes")

        remaining_dataset = policy.max_total_bytes_per_dataset - bytes_used_dataset
        remaining_run = run_budget_left_bytes - bytes_used_run
        if remaining_dataset <= 0 or remaining_run <= 0:
            break

        allowed = min(policy.max_bytes_per_file, remaining_dataset, remaining_run)

        if isinstance(size_bytes, int) and size_bytes > allowed:
            continue

        out_path = local_dir / name
        ok, nbytes = try_download_file(
            url,
            out_path,
            session=session,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            user_agent=user_agent,
            max_bytes=allowed,
        )
        if not ok:
            continue

        bytes_used_dataset += nbytes
        bytes_used_run += nbytes

        if is_qda_file(name, qda_exts):
            qda_rows.append((url, name))

    return local_dir_rel, qda_rows, bytes_used_run