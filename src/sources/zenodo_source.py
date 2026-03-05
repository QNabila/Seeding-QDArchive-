from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import requests

from src import db as dbmod
from src.download_policy import DownloadPolicy
from src.util import utc_now_iso
from src.zenodo import (
    download_record as zen_download,
    extract_license as zen_license,
    extract_uploader as zen_uploader,
    record_has_qda_file as zen_has_qda,
    search_records_overfetch as zen_search_overfetch,
)


@dataclass
class _Stats:
    scanned: int = 0
    skipped_no_license: int = 0
    skipped_no_qda: int = 0
    downloaded_datasets: int = 0
    inserted_rows: int = 0
    bytes_used: int = 0

    def as_dict(self) -> Dict:
        return {
            "scanned": self.scanned,
            "skipped_no_license": self.skipped_no_license,
            "skipped_no_qda": self.skipped_no_qda,
            "downloaded_datasets": self.downloaded_datasets,
            "inserted_rows": self.inserted_rows,
            "bytes_used": self.bytes_used,
        }


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

        remaining = run_budget_left_bytes - stats.bytes_used
        if remaining <= 0:
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
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            user_agent=user_agent,
            policy=policy,
            run_budget_left_bytes=remaining,
        )

        stats.bytes_used += int(used_bytes or 0)
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

    return stats.as_dict()