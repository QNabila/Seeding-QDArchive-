from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple

import requests

_CHUNK_SIZE = 256 * 1024


def utc_now_iso() -> str:
    # UTC ISO-like timestamp (no milliseconds) used for metadata fields.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_slug(text: str, max_len: int = 80) -> str:
    raw = (text or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    if not raw:
        raw = "dataset"
    return raw[:max_len].strip("-")


def ext_lower(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def is_qda_file(filename: str, qda_exts: Iterable[str]) -> bool:
    ext = ext_lower(filename)
    normalized: Set[str] = {str(x).lower().lstrip(".") for x in qda_exts}
    return ext in normalized


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def download_file(
    url: str,
    out_path: Path,
    *,
    session: requests.Session,
    connect_timeout: int,
    read_timeout: int,
    user_agent: str,
    max_bytes: Optional[int] = None,
) -> int:
    """
    Stream-download `url` to `out_path` using a temporary ".partial" file and then rename.
    Separate connect/read timeouts are used.
    If `max_bytes` is provided, aborts when the written size exceeds it.
    Returns the number of bytes written.
    """
    ensure_dir(out_path.parent)

    headers = {"User-Agent": user_agent}
    tmp_path = out_path.with_name(out_path.name + ".partial")

    written = 0
    try:
        with session.get(
            url,
            stream=True,
            headers=headers,
            timeout=(connect_timeout, read_timeout),
        ) as resp:
            resp.raise_for_status()

            with tmp_path.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    if not chunk:
                        continue

                    written += len(chunk)
                    if max_bytes is not None and written > max_bytes:
                        raise ValueError(f"File too large: exceeded {max_bytes} bytes")

                    fh.write(chunk)

        tmp_path.replace(out_path)
        return written

    except Exception:
        _remove_quietly(tmp_path)
        raise


def try_download_file(
    url: str,
    out_path: Path,
    *,
    session: requests.Session,
    connect_timeout: int,
    read_timeout: int,
    user_agent: str,
    max_bytes: Optional[int] = None,
) -> Tuple[bool, int]:
    """
    Best-effort download wrapper.
    Returns (ok, bytes_written). ok=False for HTTP/timeouts or max size abort.
    """
    try:
        nbytes = download_file(
            url,
            out_path,
            session=session,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            user_agent=user_agent,
            max_bytes=max_bytes,
        )
        return True, nbytes
    except (requests.RequestException, ValueError):
        return False, 0