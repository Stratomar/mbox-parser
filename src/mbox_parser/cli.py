from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mbox_parser.db import Database
from mbox_parser.parser import parse_mbox


def cmd_parse(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = Path(args.db) if args.db else output_dir / "emails.db"

    mbox_files: list[Path] = []
    if args.mbox_dir:
        mbox_dir = Path(args.mbox_dir)
        mbox_files = sorted(mbox_dir.glob("*.mbox"))
        if not mbox_files:
            print(f"No .mbox files found in {mbox_dir}", file=sys.stderr)
            sys.exit(1)
    elif args.mbox_file:
        mbox_files = [Path(args.mbox_file)]

    print(f"Output directory: {output_dir}")
    print(f"Database: {db_path}")
    print(f"Mbox files: {len(mbox_files)}")
    print()

    with Database(db_path) as db:
        db.create_tables()

        totals = {"total": 0, "inserted": 0, "skipped": 0, "errors": 0}

        for mbox_path in mbox_files:
            print(f"Parsing {mbox_path.name}...")
            stats = parse_mbox(mbox_path, db, output_dir)

            for key in totals:
                totals[key] += stats[key]

            print(
                f"  {stats['inserted']} inserted, "
                f"{stats['skipped']} skipped, "
                f"{stats['errors']} errors"
            )
            print()

    print("--- Summary ---")
    print(f"Total messages: {totals['total']}")
    print(f"Inserted: {totals['inserted']}")
    print(f"Skipped (duplicates): {totals['skipped']}")
    print(f"Errors: {totals['errors']}")


def cmd_stats(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with Database(db_path) as db:
        row = db.conn.execute("SELECT COUNT(*) as cnt FROM emails").fetchone()
        print(f"Total emails: {row['cnt']}")

        row = db.conn.execute(
            "SELECT MIN(date) as min_date, MAX(date) as max_date FROM emails WHERE date IS NOT NULL"
        ).fetchone()
        print(f"Date range: {row['min_date']} to {row['max_date']}")

        print("\nTop 10 senders:")
        rows = db.conn.execute(
            "SELECT from_address, COUNT(*) as cnt FROM emails "
            "GROUP BY from_address ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print(f"  {r['cnt']:>6}  {r['from_address']}")

        print("\nLabel distribution:")
        label_counts: dict[str, int] = {}
        rows = db.conn.execute("SELECT labels FROM emails").fetchall()
        for r in rows:
            for label in json.loads(r["labels"]):
                label_counts[label] = label_counts.get(label, 0) + 1
        for label, count in sorted(label_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"  {count:>6}  {label}")

        row = db.conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(size_bytes), 0) as total_size FROM attachments"
        ).fetchone()
        size_mb = row["total_size"] / (1024 * 1024)
        print(f"\nAttachments: {row['cnt']} ({size_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mbox-parser",
        description="Parse Gmail mbox exports into a SQLite database",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subparsers.add_parser("parse", help="Parse mbox files")
    group = parse_cmd.add_mutually_exclusive_group(required=True)
    group.add_argument("--mbox-dir", help="Directory containing .mbox files")
    group.add_argument("--mbox-file", help="Single .mbox file to parse")
    parse_cmd.add_argument(
        "--output-dir", default="./output", help="Output directory (default: ./output)"
    )
    parse_cmd.add_argument(
        "--db", help="Database path (default: {output-dir}/emails.db)"
    )
    parse_cmd.set_defaults(func=cmd_parse)

    stats_cmd = subparsers.add_parser("stats", help="Show database statistics")
    stats_cmd.add_argument("--db", required=True, help="Database path")
    stats_cmd.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)
