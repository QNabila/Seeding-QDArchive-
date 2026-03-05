from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

import db as dbmod
from dataverse import (
    download_dataset as dv_download,
    extract_license as dv_license,
    get_dataset_details,
    record_has_qda_or_zip as dv_has_qda_or_zip,
    search_dataverse,
)
from download_policy import policy_from_config
from qda_exts import load_qda_extensions
from util import ensure_dir, utc_now_iso
from zenodo import (
    download_record as zen_download,
    extract_license as zen_license,
    extract_uploader as zen_uploader,
    record_has_qda_file as zen_has_qda,
    search_records_overfetch as zen_search_overfetch,
)


@dataclass
class RepoStats:
    scanned: int = 0
    skipped_no_license: int = 0
    skipped_no_qda: int = 0
    downloaded_datasets: int = 0
    inserted_rows: int = 0


def _read_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.json")
    p.add_argument("--limit", type=int, default=10)
    return p.parse_args()


def _remaining_run_budget(max_total: int, used: int) -> int:
    left = max_total - used
    return left if left > 0 else 0


def _run_zenodo(
    *,
    session: requests.Session,
    conn,
    downloads_root: Path,
    qda_exts: List[str],
    timeout: int,
    user_agent: str,
    policy,
    limit: int,
    run_bytes_used: int,
) -> Tuple[RepoStats, int]:
    stats = RepoStats()

    overfetch = max(limit * 30, 100)
    candidates = zen_search_overfetch(
        qda_exts=qda_exts,
        session=session,
        timeout=timeout,
        user_agent=user_agent,
        overfetch=overfetch,
    )

    for rec in candidates:
        if stats.downloaded_datasets >= limit:
            break
        if run_bytes_used >= policy.max_total_bytes_per_run:
            break

        stats.scanned += 1

        lic = zen_license(rec)
        if not lic:
            stats.skipped_no_license += 1
            continue

        if not zen_has_qda(rec, qda_exts):
            stats.skipped_no_qda += 1
            continue

        uploader_name, uploader_email = zen_uploader(rec)

        local_dir_rel, qda_rows, used_bytes = zen_download(
            record=rec,
            downloads_root=downloads_root,
            qda_exts=qda_exts,
            session=session,
            timeout=timeout,
            user_agent=user_agent,
            policy=policy,
            run_budget_left_bytes=_remaining_run_budget(policy.max_total_bytes_per_run, run_bytes_used),
        )

        run_bytes_used += used_bytes
        stats.downloaded_datasets += 1

        ts = utc_now_iso()
        for qda_url, qda_filename in qda_rows:
            dbmod.insert_acquisition(
                conn,
                qda_file_url=qda_url,
                download_timestamp=ts,
                local_dir=local_dir_rel,
                local_qda_filename=qda_filename,
                context_repository="Zenodo",
                license_str=lic,
                uploader_name=uploader_name,
                uploader_email=uploader_email,
            )
            stats.inserted_rows += 1

    return stats, run_bytes_used


def _run_dataverse(
    *,
    session: requests.Session,
    conn,
    downloads_root: Path,
    qda_exts: List[str],
    timeout: int,
    user_agent: str,
    policy,
    limit: int,
    run_bytes_used: int,
) -> Tuple[RepoStats, int]:
    stats = RepoStats()

    dv_items = search_dataverse(
        session=session,
        timeout=timeout,
        user_agent=user_agent,
        limit=max(limit * 15, 150),
    )

    for item in dv_items:
        if stats.downloaded_datasets >= limit:
            break
        if run_bytes_used >= policy.max_total_bytes_per_run:
            break

        stats.scanned += 1

        pid = item.get("global_id") or item.get("globalId")
        if not pid:
            continue

        ds_json = get_dataset_details(
            persistent_id=pid,
            session=session,
            timeout=timeout,
            user_agent=user_agent,
        )

        lic = dv_license(ds_json)
        if not lic:
            stats.skipped_no_license += 1
            continue

        if not dv_has_qda_or_zip(ds_json, qda_exts):
            stats.skipped_no_qda += 1
            continue

        local_dir_rel, qda_rows, used_bytes = dv_download(
            dataset_item=item,
            dataset_json=ds_json,
            downloads_root=downloads_root,
            qda_exts=qda_exts,
            session=session,
            timeout=timeout,
            user_agent=user_agent,
            policy=policy,
            run_budget_left_bytes=_remaining_run_budget(policy.max_total_bytes_per_run, run_bytes_used),
        )

        run_bytes_used += used_bytes

        # keep behavior: do not count dataset as "downloaded" if it produced no qda rows
        if not qda_rows:
            continue

        stats.downloaded_datasets += 1

        ts = utc_now_iso()
        for qda_url, qda_filename in qda_rows:
            dbmod.insert_acquisition(
                conn,
                qda_file_url=qda_url,
                download_timestamp=ts,
                local_dir=local_dir_rel,
                local_qda_filename=qda_filename,
                context_repository="DataverseNO",
                license_str=str(lic),
                uploader_name=None,
                uploader_email=None,
            )
            stats.inserted_rows += 1

    return stats, run_bytes_used


def main() -> None:
    args = _parse_args()
    cfg = _read_config(Path(args.config))

    downloads_root = Path(cfg["downloads_root"])
    sqlite_path = Path(cfg["sqlite_path"])
    qda_xlsx = Path(cfg.get("qda_extensions_xlsx", "QDA File Extensions Formats.xlsx"))
    timeout = int(cfg.get("http_timeout_sec", 60))
    user_agent = str(cfg.get("user_agent", "SeedingQDArchive/Part1"))

    ensure_dir(downloads_root)

    qda_exts = load_qda_extensions(qda_xlsx)
    policy = policy_from_config(cfg, qda_exts)

    conn = dbmod.connect(sqlite_path)
    dbmod.init_db(conn)

    run_bytes_used = 0
    zen_stats = RepoStats()
    dv_stats = RepoStats()

    with requests.Session() as session:
        zen_stats, run_bytes_used = _run_zenodo(
            session=session,
            conn=conn,
            downloads_root=downloads_root,
            qda_exts=qda_exts,
            timeout=timeout,
            user_agent=user_agent,
            policy=policy,
            limit=args.limit,
            run_bytes_used=run_bytes_used,
        )

        dv_stats, run_bytes_used = _run_dataverse(
            session=session,
            conn=conn,
            downloads_root=downloads_root,
            qda_exts=qda_exts,
            timeout=timeout,
            user_agent=user_agent,
            policy=policy,
            limit=args.limit,
            run_bytes_used=run_bytes_used,
        )

    out_csv = Path("metadata.csv")
    dbmod.export_csv(conn, out_csv)

    print("Done.")
    print("Zenodo scanned:", zen_stats.scanned)
    print("Zenodo skipped (no license):", zen_stats.skipped_no_license)
    print("Zenodo skipped (no QDA file detected):", zen_stats.skipped_no_qda)
    print("Zenodo downloaded datasets:", zen_stats.downloaded_datasets)
    print("Zenodo inserted QDA rows:", zen_stats.inserted_rows)
    print("DataverseNO scanned:", dv_stats.scanned)
    print("DataverseNO skipped (no license):", dv_stats.skipped_no_license)
    print("DataverseNO skipped (no QDA file detected):", dv_stats.skipped_no_qda)
    print("DataverseNO downloaded datasets:", dv_stats.downloaded_datasets)
    print("DataverseNO inserted QDA rows:", dv_stats.inserted_rows)
    print("Run downloaded bytes:", run_bytes_used)
    print("Downloads folder:", downloads_root.resolve())
    print("SQLite DB:", sqlite_path.resolve())
    print("CSV export:", out_csv.resolve())


if __name__ == "__main__":
    main()