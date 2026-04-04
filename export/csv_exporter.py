"""
CSV Exporter
Exports all database tables to CSV files in the export/ directory.
"""

import csv
from pathlib import Path
from db.database import get_connection

EXPORT_DIR = Path(__file__).parent.parent / "export" / "csv"


def export_table(conn, table_name, output_path):
    """Export a single table to a CSV file."""
    rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    if not rows:
        print(f"  [SKIP] {table_name} is empty.")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(rows[0].keys())  # header
        for row in rows:
            writer.writerow(list(row))

    print(f"  Exported {len(rows)} rows -> {output_path.name}")
    return len(rows)


def export_to_csv():
    """Export all tables to CSV files."""
    print("\n=== Exporting to CSV ===")
    conn = get_connection()

    tables = ["REPOSITORIES", "PROJECTS", "FILES", "KEYWORDS", "PERSON_ROLE", "LICENSES"]
    total = 0
    for table in tables:
        out_path = EXPORT_DIR / f"{table.lower()}.csv"
        total += export_table(conn, table, out_path)

    conn.close()
    print(f"  Total rows exported: {total}")
    print(f"  CSV files saved to: {EXPORT_DIR}")
