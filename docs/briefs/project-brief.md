# Project Brief — mbox-parser

## Overview

CLI tool that parses Gmail mbox exports (from Google Takeout) into a deduplicated SQLite database. Extracts email metadata, bodies, attachments, Gmail labels, and Google Chat messages.

## Target Users

Personal use — archiving and querying Gmail exports locally.

## Goals

- Parse mbox files into a queryable SQLite database
- Deduplicate emails by Message-ID
- Extract and save attachments to disk
- Handle Google Chat messages embedded in mbox exports

## Non-goals

- No web UI or API server
- No IMAP/POP3 live fetching
- No full-text search beyond what SQLite provides natively

## Tech Stack

| Component  | Choice       | Rationale                                    |
|------------|-------------|----------------------------------------------|
| Language   | Python 3.11+ | stdlib `mailbox` module handles mbox natively |
| Database   | SQLite (WAL) | Zero-config, single-file, portable            |
| HTML→text  | html2text    | Lightweight conversion for HTML-only emails   |
| Progress   | tqdm         | Progress bars for large mbox files            |
| Linting    | ruff         | Fast, all-in-one Python linter/formatter      |
| Typechecking | mypy       | Static type safety                           |
| Testing    | pytest       | Standard Python test runner                   |

## Architecture

Single-process CLI with three layers:

1. **CLI** (`cli.py`) — argparse subcommands (`parse`, `stats`)
2. **Parser** (`parser.py`) — iterates mbox messages, delegates to extractors, writes to DB
3. **Extractors** (`extractors.py`, `chat.py`) — decode headers, bodies, attachments, and Chat XML

Data flow: mbox file → `mailbox.mbox` iterator → extract fields → insert into SQLite → save attachments to disk.

## Data Model

**emails** — one row per unique Message-ID. Stores sender, recipients (JSON arrays), date, subject, text/HTML body, Gmail labels, thread ID, chat flag.

**attachments** — linked to emails by foreign key. Stores filename, MIME type, size, and relative file path.

## Infrastructure

Local only. No deployment, no CI/CD.

## Constraints & Risks

- Large mbox files (multi-GB) require streaming; current approach loads via Python's `mailbox.mbox` which is memory-mapped
- Gmail label parsing depends on the `X-Gmail-Labels` header (Takeout-specific)
- Chat XML parsing assumes Google's `google:archive:conversation` namespace

## References

- Changelog: `CHANGELOG.md`
