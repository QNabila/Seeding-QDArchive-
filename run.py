from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from src import db as dbmod
from src.download_policy import policy_from_config
from src.qda_exts import load_qda_extensions
from src.util import ensure_dir


@dataclass(frozen=True)
class RuntimeSettings:
    downloads_root: Path
    sqlite_path: Path
    csv_path: Path
    qda_xlsx: Path
    connect_timeout: int
    read_timeout: int
    api_timeout: int
    user_agent: str
    sources: List[str]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def _build_settings(cfg: Dict[str, Any]) -> RuntimeSettings:
    downloads_root = Path(cfg["downloads_root"])
    sqlite_path = Path(cfg["sqlite_path"])
    csv_path = Path(cfg.get("csv_path", "metadata.csv"))
    qda_xlsx = Path(cfg.get("qda_extensions_xlsx", "QDA File Extensions Formats.xlsx"))

    connect_timeout = int(cfg.get("http_connect_timeout_sec", 15))
    read_timeout = int(cfg.get("http_read_timeout_sec", 30))
    api_timeout = int(cfg.get("http_timeout_sec", max(connect_timeout, read_timeout)))

    user_agent = str(cfg.get("user_agent", "SeedingQDArchive/Part1"))
    sources = list(cfg.get("sources") or [])

    return RuntimeSettings(
        downloads_root=downloads_root,
        sqlite_path=sqlite_path,
        csv_path=csv_path,
        qda_xlsx=qda_xlsx,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        api_timeout=api_timeout,
        user_agent=user_agent,
        sources=sources,
    )


def _import_source(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        # allow config entries like "sources.zenodo_source"
        return importlib.import_module(f"src.{name}")


def _print_source_stats(src: str, stats: Dict[str, Any]) -> int:
    used = int(stats.get("bytes_used") or 0)

    print(f"{src}_scanned:", stats.get("scanned", 0))
    print(f"{src}_skipped_no_license:", stats.get("skipped_no_license", 0))
    print(f"{src}_skipped_no_qda:", stats.get("skipped_no_qda", 0))
    print(f"{src}_downloaded_datasets:", stats.get("downloaded_datasets", 0))
    print(f"{src}_inserted_qda_rows:", stats.get("inserted_rows", 0))
    print(f"{src}_bytes_used:", used)

    return used


def main() -> None:
    args = _parse_args()
    cfg = _read_json(Path(args.config))
    settings = _build_settings(cfg)

    ensure_dir(settings.downloads_root)

    qda_exts = load_qda_extensions(settings.qda_xlsx)
    print("Loaded QDA extensions:", len(qda_exts))

    policy = policy_from_config(cfg, qda_exts)
    total_bytes_used = 0

    conn = dbmod.connect(settings.sqlite_path)
    dbmod.init_db(conn)

    with requests.Session() as session:
        for src in settings.sources:
            print("\nRunning source:", src)

            remaining = policy.max_total_bytes_per_run - total_bytes_used
            if remaining <= 0:
                print("Run budget reached, stopping.")
                break

            module = _import_source(src)

            stats: Dict[str, Any] = module.acquire(
                conn=conn,
                qda_exts=qda_exts,
                session=session,
                timeout=settings.api_timeout,
                user_agent=settings.user_agent,
                downloads_root=settings.downloads_root,
                limit=args.limit,
                policy=policy,
                run_budget_left_bytes=remaining,
                connect_timeout=settings.connect_timeout,
                read_timeout=settings.read_timeout,
                cfg=cfg,
            )

            total_bytes_used += _print_source_stats(src, stats)

    dbmod.export_csv(conn, settings.csv_path)

    print("\nDone.")
    print("Downloads folder:", settings.downloads_root.resolve())
    print("SQLite DB:", settings.sqlite_path.resolve())
    print("CSV export:", settings.csv_path.resolve())
    print("Run downloaded bytes:", total_bytes_used)


if __name__ == "__main__":
    main()