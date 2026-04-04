import requests
import time
from pathlib import Path
from db.database import (
    STATUS_SUCCESS, STATUS_LOGIN_REQUIRED,
    STATUS_HTTP_404, STATUS_HTTP_ERROR, STATUS_TIMEOUT
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def download_file(url, dest_path, extra_headers=None):
    """Download a single file to dest_path. Returns a status string."""
    if dest_path.exists():
        return STATUS_SUCCESS

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {**HEADERS, **(extra_headers or {})}

    try:
        r = requests.get(url, headers=headers, timeout=120, stream=True)

        if r.status_code == 200:
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            time.sleep(0.5)  # polite delay
            return STATUS_SUCCESS
        elif r.status_code in (401, 403):
            return STATUS_LOGIN_REQUIRED
        elif r.status_code == 404:
            return STATUS_HTTP_404
        elif r.status_code == 429:
            return "FAILED_HTTP_429"
        else:
            return f"FAILED_HTTP_{r.status_code}"

    except requests.Timeout:
        return STATUS_TIMEOUT
    except Exception as e:
        print(f"  [DL ERROR] {url}: {e}")
        return STATUS_HTTP_ERROR
