from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from src.util import ext_lower, is_qda_file


@dataclass(frozen=True)
class DownloadPolicy:
    max_files_per_dataset: int
    max_total_bytes_per_dataset: int
    max_bytes_per_file: int
    max_total_bytes_per_run: int

    download_primary_data: bool
    allowed_primary_exts: Set[str]
    skip_exts: Set[str]

    qda_exts: List[str]


def _mb(value: int) -> int:
    return int(value) * 1024 * 1024


def policy_from_config(cfg: dict, qda_exts: List[str]) -> DownloadPolicy:
    dp = cfg.get("download_policy") or {}

    allowed = {str(x).lower().lstrip(".") for x in dp.get("allowed_primary_exts", [])}
    skipped = {str(x).lower().lstrip(".") for x in dp.get("skip_exts", [])}

    return DownloadPolicy(
        max_files_per_dataset=int(dp.get("max_files_per_dataset", 25)),
        max_total_bytes_per_dataset=_mb(int(dp.get("max_total_mb_per_dataset", 800))),
        max_bytes_per_file=_mb(int(dp.get("max_mb_per_file", 250))),
        max_total_bytes_per_run=_mb(int(dp.get("max_total_mb_per_run", 5000))),
        download_primary_data=bool(dp.get("download_primary_data", True)),
        allowed_primary_exts=allowed,
        skip_exts=skipped,
        qda_exts=list(qda_exts),
    )


def is_allowed(filename: str, policy: DownloadPolicy) -> Tuple[bool, str]:
    ext = ext_lower(filename)

    if ext in policy.skip_exts:
        return False, f"skip_ext:{ext}"

    if is_qda_file(filename, policy.qda_exts):
        return True, f"qda_ext:{ext}"

    if policy.download_primary_data and ext in policy.allowed_primary_exts:
        return True, f"primary_ext:{ext}"

    return False, f"not_allowed_ext:{ext}"


def select_files(files: List[Dict], policy: DownloadPolicy) -> List[Dict]:
    """
    Input dict fields:
      name: str
      url: str
      size_bytes: int | None

    Output dict adds:
      reason: str
      is_qda: bool
    """
    candidates: List[Dict] = []

    for item in files:
        name = (item.get("name") or "").strip()
        ok, reason = is_allowed(name, policy)
        if not ok:
            continue

        enriched = dict(item)
        enriched["reason"] = reason
        enriched["is_qda"] = is_qda_file(name, policy.qda_exts)
        candidates.append(enriched)

    candidates.sort(key=lambda x: (0 if x.get("is_qda") else 1, x.get("name", "")))

    picked: List[Dict] = []
    total_known_bytes = 0

    for f in candidates:
        if len(picked) >= policy.max_files_per_dataset:
            break

        size = f.get("size_bytes")
        if isinstance(size, int):
            if size > policy.max_bytes_per_file:
                continue
            if total_known_bytes + size > policy.max_total_bytes_per_dataset:
                continue

        picked.append(f)

        if isinstance(size, int):
            total_known_bytes += size

    return picked
