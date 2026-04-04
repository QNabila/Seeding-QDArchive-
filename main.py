#!/usr/bin/env python3
"""
QDArchive — Part 1: Data Acquisition Pipeline
FAU Erlangen — Seeding QDArchive

Repositories:
  8  - DataFirst UCT     (https://datafirst.uct.ac.za)
  18 - Harvard Murray    (https://www.murray.harvard.edu)

Usage:
  python3 main.py                      # run all scrapers + export
  python3 main.py --source datafirst   # run only DataFirst
  python3 main.py --source harvard     # run only Harvard
  python3 main.py --stats              # show statistics
  python3 main.py --export             # export CSV only
"""

import argparse
from pathlib import Path
from db.database import init_db, get_project_count, get_file_status_summary
from scrapers import datafirst_scraper, harvard_scraper
from export.csv_exporter import export_to_csv

DATA_ROOT = Path(__file__).parent / "data"


def main():
    parser = argparse.ArgumentParser(
        description="QDArchive Part 1 — Data Acquisition Pipeline"
    )
    parser.add_argument(
        "--source",
        choices=["datafirst", "harvard", "all"],
        default="all",
        help="Which repository to scrape (default: all)"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export database to CSV files"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  QDArchive Part 1 — Data Acquisition Pipeline")
    print("=" * 50)

    print("\nInitializing database...")
    init_db()

    if args.stats:
        print(f"\nTotal projects: {get_project_count()}")
        summary = get_file_status_summary()
        if summary:
            print("File status summary:")
            for status, count in sorted(summary.items()):
                print(f"  {status:<45} {count}")
        else:
            print("  No files recorded yet.")
        return

    if args.export:
        export_to_csv()
        return

    # Run scrapers
    if args.source in ("datafirst", "all"):
        datafirst_scraper.run(DATA_ROOT)

    if args.source in ("harvard", "all"):
        harvard_scraper.run(DATA_ROOT)

    # Export and stats
    print("\nExporting to CSV...")
    export_to_csv()

    print("\nFinal Statistics:")
    print(f"  Total projects: {get_project_count()}")
    summary = get_file_status_summary()
    for status, count in sorted(summary.items()):
        print(f"  {status:<45} {count}")

    print("\nDone!")


if __name__ == "__main__":
    main()
