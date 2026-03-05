from __future__ import annotations

from pathlib import Path
from typing import List, Set

import openpyxl

# Baseline list (always included) even if the spreadsheet is missing or incomplete.
DEFAULT_QDA_EXTS: List[str] = [
    # REFI-QDA
    "qdpx",
    "qdc",
    # NVivo
    "nvpx",
    "nvp",
    # ATLAS.ti
    "atlasproj",
    "hpr7",
    # MAXQDA (common)
    "mqda",
    "mx24",
    "mx24bac",
    "mx22",
    "mx20",
    "mx18",
    "mx12",
    "mx11",
    "mx5",
    "mx4",
    "mx3",
    "mx2",
    "m2k",
]


def _looks_like_extension(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower().lstrip(".")
    if not (2 <= len(s) <= 30):
        return None
    allowed = all(ch.isalnum() or ch in {"_", "-"} for ch in s)
    return s if allowed else None


def load_qda_extensions(xlsx_path: Path) -> List[str]:
    """
    Loads QDA file extensions from an xlsx file (all cells in the active sheet).
    Always merges with DEFAULT_QDA_EXTS and removes known false-positive 'qdp'.
    """
    exts: Set[str] = set(DEFAULT_QDA_EXTS)

    if not xlsx_path.exists():
        # spreadsheet is optional
        exts.discard("qdp")
        return sorted(exts)

    wb = openpyxl.load_workbook(str(xlsx_path))
    ws = wb.active

    for row in ws.iter_rows(values_only=True):
        for cell in row:
            ext = _looks_like_extension(cell)
            if ext:
                exts.add(ext)

    # Remove known bad extension for qualitative QDA search
    exts.discard("qdp")

    return sorted(exts)