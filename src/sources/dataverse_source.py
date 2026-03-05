from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import requests

from src import db as dbmod
from src.dataverse import (
    download_dataset as dv_download,
    extract_license as dv_license,
    get_dataset_details,
    record_has_qda_or_zip as dv_has_qda_or_zip,
    search_dataverse,
)
from src.download_policy import DownloadPolicy
from src.util import utc_now_iso


@dataclass
class _Stats:
    scanned: int = 0
    skipped_no_license: int = 0
    skipped_no_qda: int = 0
    downloaded_datasets: int = 0
    inserted_rows: int = 0
    bytes_used: int = 0

    def to_dict(self) -> Dict:
        return {
            "scanned": self.scanned,
            "skipped_no_license": self.skipped_no_license,
            "skipped_no_qda": self.skipped_no_qda,
            "downloaded_datasets": self.downloaded_datasets,
            "inserted_rows": self.inserted_rows,
            "bytes_used": self.bytes_used,
        }


def _should_download_primary_only_if_qda(cfg: dict) -> bool:
    dp = cfg.get("download_policy") or {}
    return bool(dp.get("dataverse_download_primary_only_if_qda_present", True))


def acquire(
    *,
    conn,
    qda_exts: List[str],
    session: requests.Session,
    timeout: int,
    user_agent: str,
    downloads_root,
    limit: int,
    policy: DownloadPolicy,
    run_budget_left_bytes: int,
    connect_timeout: int,
    read_timeout: int,
    cfg: dict,
) -> Dict:
    stats = _Stats()
    only_if_qda = _should_download_primary_only_if_qda(cfg)

    items = search_dataverse(
        session=session,
        timeout=timeout,
        user_agent=user_agent,
        limit=max(limit * 15, 150),
    )

    for item in items:
        if stats.downloaded_datasets >= limit:
            break

        remaining = run_budget_left_bytes - stats.bytes_used
        if remaining <= 0:
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
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            user_agent=user_agent,
            policy=policy,
            run_budget_left_bytes=remaining,
            dataverse_download_primary_only_if_qda_present=only_if_qda,
        )

        stats.bytes_used += int(used_bytes or 0)

        # keep behavior: don't count as downloaded unless we found QDA rows
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

    return stats.to_dict()