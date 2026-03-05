from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from src.download_policy import DownloadPolicy, select_files
from src.util import ensure_dir, is_qda_file, safe_slug, try_download_file

DATAVERSE_BASE = "https://dataverse.no"
SEARCH_API = f"{DATAVERSE_BASE}/api/search"
DATASET_API = f"{DATAVERSE_BASE}/api/datasets"


def search_dataverse(
    *,
    session: requests.Session,
    timeout: int,
    user_agent: str,
    limit: int,
) -> List[Dict]:
    q = (
        '(qualitative OR interview OR transcript OR "focus group" OR NVivo OR MAXQDA '
        'OR "Atlas.ti" OR REFI OR QDA OR qdpx OR nvpx OR atlasproj OR mx24 OR mx22 OR mx20)'
    )
    headers = {"User-Agent": user_agent}

    items: List[Dict] = []
    start = 0
    per_page = 50
    hard_cap = 2000

    while len(items) < limit and start <= hard_cap:
        resp = session.get(
            SEARCH_API,
            params={
                "q": q,
                "type": "dataset",
                "start": start,
                "per_page": per_page,
                "sort": "date",
                "order": "desc",
            },
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()

        payload = resp.json()
        batch = ((payload.get("data") or {}).get("items") or [])
        if not batch:
            break

        items.extend(batch)
        start += per_page

    return items[:limit]


def get_dataset_details(
    *,
    persistent_id: str,
    session: requests.Session,
    timeout: int,
    user_agent: str,
) -> Dict:
    url = f"{DATASET_API}/:persistentId/?persistentId={persistent_id}"
    resp = session.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def extract_license(dataset_json: Dict) -> Optional[str]:
    data = dataset_json.get("data") or {}

    for key in ("termsOfUse", "license"):
        val = data.get(key)
        if val and str(val).strip():
            return str(val).strip()

    latest = data.get("latestVersion") or {}
    for key in ("termsOfUse", "license"):
        val = latest.get(key)
        if val and str(val).strip():
            return str(val).strip()

    blocks = latest.get("metadataBlocks") or {}
    for block in blocks.values():
        fields = block.get("fields") or []
        for field in fields:
            name = (field.get("typeName") or "").lower()
            value = field.get("value")

            if not any(k in name for k in ("license", "terms", "rights", "conditions")):
                continue

            if isinstance(value, str) and value.strip():
                return value.strip()

            if isinstance(value, list):
                joined = " ; ".join(str(x).strip() for x in value if str(x).strip())
                if joined:
                    return joined

    return None


def dataset_files(dataset_json: Dict) -> List[Dict]:
    data = dataset_json.get("data") or {}
    latest = data.get("latestVersion") or {}
    files = latest.get("files") or []
    return files if isinstance(files, list) else []


def _is_zip(filename: str) -> bool:
    return (filename or "").lower().endswith(".zip")


def qda_files_inside_zip(zip_path: Path, qda_exts: List[str]) -> List[str]:
    found: List[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                if is_qda_file(name, qda_exts):
                    found.append(name)
    except zipfile.BadZipFile:
        return []
    return found


def record_has_qda_or_zip(dataset_json: Dict, qda_exts: List[str]) -> bool:
    for f in dataset_files(dataset_json):
        df = (f or {}).get("dataFile") or {}
        name = df.get("filename")
        if not name:
            continue
        if is_qda_file(name, qda_exts) or _is_zip(name):
            return True
    return False


def _budget_for_next_file(
    *,
    policy: DownloadPolicy,
    used_dataset: int,
    used_run: int,
    run_budget_left_bytes: int,
) -> int:
    remaining_dataset = policy.max_total_bytes_per_dataset - used_dataset
    remaining_run = run_budget_left_bytes - used_run
    if remaining_dataset <= 0 or remaining_run <= 0:
        return 0
    return min(policy.max_bytes_per_file, remaining_dataset, remaining_run)


def download_dataset(
    *,
    dataset_item: Dict,
    dataset_json: Dict,
    downloads_root: Path,
    qda_exts: List[str],
    session: requests.Session,
    connect_timeout: int,
    read_timeout: int,
    user_agent: str,
    policy: DownloadPolicy,
    run_budget_left_bytes: int,
    dataverse_download_primary_only_if_qda_present: bool = True,
) -> Tuple[str, List[Tuple[str, str]], int]:
    title = dataset_item.get("name") or "dataverse-dataset"
    slug = safe_slug(title)

    local_dir_rel = f"dataverseno/{slug}"
    local_dir = downloads_root / local_dir_rel
    ensure_dir(local_dir)

    (local_dir / "metadata.json").write_text(
        json.dumps(dataset_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    files = dataset_files(dataset_json)

    qda_present = any(
        is_qda_file(((f.get("dataFile") or {}).get("filename") or ""), qda_exts) for f in files
    )
    zip_present = any(_is_zip(((f.get("dataFile") or {}).get("filename") or "")) for f in files)

    allow_primary = policy.download_primary_data
    if dataverse_download_primary_only_if_qda_present:
        allow_primary = allow_primary and (qda_present or zip_present)

    candidates: List[Dict] = []
    for f in files:
        df = f.get("dataFile") or {}
        file_id = df.get("id")
        filename = df.get("filename")
        if not file_id or not filename:
            continue

        url = f"{DATAVERSE_BASE}/api/access/datafile/{file_id}"

        raw_size = df.get("filesize")
        size_bytes = raw_size if isinstance(raw_size, int) else None

        ext = Path(filename).suffix.lower().lstrip(".")
        is_qda = is_qda_file(filename, qda_exts)
        is_zip = _is_zip(filename)
        is_primary = allow_primary and (ext in policy.allowed_primary_exts)

        if not (is_qda or is_zip or is_primary):
            continue

        candidates.append({"name": filename, "url": url, "size_bytes": size_bytes})

    selected = select_files(candidates, policy)

    qda_rows: List[Tuple[str, str]] = []
    used_dataset = 0
    used_run = 0

    for f in selected:
        name = f["name"]
        url = f["url"]
        size_bytes = f.get("size_bytes")

        allowed = _budget_for_next_file(
            policy=policy,
            used_dataset=used_dataset,
            used_run=used_run,
            run_budget_left_bytes=run_budget_left_bytes,
        )
        if allowed <= 0:
            break

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

        used_dataset += nbytes
        used_run += nbytes

        if is_qda_file(name, qda_exts):
            qda_rows.append((url, name))
            continue

        if _is_zip(name):
            for inner in qda_files_inside_zip(out_path, qda_exts):
                qda_rows.append((f"{url}#{inner}", f"{name}::{inner}"))

    return local_dir_rel, qda_rows, used_run