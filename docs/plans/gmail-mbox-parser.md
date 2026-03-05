# Gmail Mbox Parser

## Description

Parse 7 Gmail mbox files (~17GB total) exported from Google Takeout into a single deduplicated SQLite database. Extract everything: full metadata (from, to, cc, bcc, date, subject, message-id, thread-id, references), body text and HTML, Gmail labels, and attachments saved to disk.

Key decisions:
- **SQLite** — zero-setup, single-file portable, Python built-in. No server infrastructure for a personal tool.
- **Deduplicate on Message-ID** — the same email appears in multiple mbox files (Inbox + Important + Archived). One row per unique message, labels captured from whichever file is parsed first.
- **Selective attachments** — save real attachments (PDFs, documents, photos, archives) to disk. Skip junk: inline tracking pixels (<5KB images without filename), `.ics` calendar files, small inline signature images.
- **Streaming** — process one message at a time via `mailbox.mbox` iterator. Never load the full file into memory.
- **Chat messages** — Google Chat exports use XML body format (`google:archive:conversation`). Parse these separately into readable text.

Reference code: [alejandro-g-m/Gmail-MBOX-email-parser](https://github.com/alejandro-g-m/Gmail-MBOX-email-parser) — patterns for multipart extraction, subject decoding, html2text conversion.

Data observations from sampling the mbox files:
- Gmail headers: `X-Gmail-Labels` (comma-separated), `X-GM-THRID` (thread ID)
- Multipart nesting: `multipart/mixed` → `multipart/related` → `multipart/alternative` → `text/plain` + `text/html`
- Attachments: `Content-Disposition: attachment; filename="..."`
- Chat messages: no Date/Subject, XML body in `text/xml` parts
- Encoded subjects: UTF-8 quoted-printable, multi-part encoded headers

Existing project scaffold: `pyproject.toml` (Python >=3.11, ruff/pytest/mypy), `Makefile` (format/lint/typecheck/test), `src/mbox_parser/__init__.py`, `tests/__init__.py`, `.venv` with Python 3.14.

## Plan

### ~~1. Dependencies and project config~~

1.1. Update `pyproject.toml` — add `html2text` and `tqdm` as runtime dependencies, add `[project.scripts]` entry point `mbox-parser = "mbox_parser.cli:main"`
1.2. Create `src/mbox_parser/__main__.py` — thin wrapper calling `cli.main()` to enable `python -m mbox_parser`
1.3. Update `.gitignore` — add `output/`, `*.db`, `mbox/` to prevent committing data files
1.4. Install dependencies — `pip install -e ".[dev]"` in the venv

### ~~2. Database layer~~

2.1. Create `src/mbox_parser/db.py` with class `Database`:
  - `__init__(self, db_path)` — open SQLite connection with WAL mode and `journal_mode=wal`, `synchronous=normal` for write performance
  - `create_tables()` — execute schema DDL:
    - `emails` table: `id` (PK), `message_id` (TEXT UNIQUE), `thread_id`, `in_reply_to`, `references`, `from_name`, `from_address`, `to_addresses` (JSON), `cc_addresses` (JSON), `bcc_addresses` (JSON), `date` (ISO 8601), `subject`, `body_text`, `body_html`, `labels` (JSON array), `source_file`, `content_type`, `is_chat` (INTEGER DEFAULT 0), `has_attachments` (INTEGER DEFAULT 0), `created_at` (datetime default)
    - `attachments` table: `id` (PK), `email_id` (FK → emails.id), `filename`, `content_type`, `size_bytes`, `file_path` (relative path on disk)
    - Indexes on: `message_id`, `thread_id`, `from_address`, `date`, `labels`, `attachments.email_id`
  - `insert_email(data: dict) -> int | None` — `INSERT OR IGNORE` on message_id, return `lastrowid` or `None` if duplicate
  - `insert_attachment(data: dict)` — insert attachment row linked by `email_id`
  - `commit()` — explicit commit for batch control
  - `close()` — close connection
  - Context manager support (`__enter__`/`__exit__`)

2.2. Create `tests/test_db.py` — test table creation, insert, deduplication, attachment linking using in-memory SQLite

### ~~3. Extractors~~

3.1. Create `src/mbox_parser/extractors.py` with pure functions:
  - `parse_address(header_value: str | None) -> dict` — use `email.utils.parseaddr`, return `{"name": ..., "address": ...}`
  - `parse_address_list(header_value: str | None) -> list[dict]` — use `email.utils.getaddresses` for To/Cc/Bcc fields
  - `decode_subject(subject) -> str` — handle `email.header.Header` objects, multi-part encoded headers (`=?UTF-8?Q?...?=`, `=?ISO-...?=`), None subjects. Pattern from reference repo's CustomMessage constructor.
  - `parse_date(date_str: str | None) -> str | None` — `email.utils.parsedate_to_datetime` → `.isoformat()`, return None on failure
  - `parse_labels(label_str: str | None) -> list[str]` — split `X-Gmail-Labels` on commas, strip whitespace, return as list
  - `extract_body(message) -> tuple[str | None, str | None]` — walk multipart tree:
    - Collect first `text/plain` part and first `text/html` part
    - Decode payload: try utf-8, fall back to latin-1
    - If no `text/plain` but have `text/html`: convert HTML → text using `html2text.HTML2Text` (ignore_links, ignore_images, ignore_tables, ignore_emphasis)
    - Strip `\r` and collapse excessive whitespace
    - Return `(body_text, body_html)`
  - `extract_attachments(message, output_dir: Path, email_id: int) -> list[dict]` — walk parts:
    - Check `Content-Disposition` for `attachment` or `inline` with a filename
    - **Skip junk**: inline images <5KB without explicit filename, `.ics` files, `text/calendar` parts
    - Save to `{output_dir}/attachments/{email_id}/{filename}`, handle duplicate filenames with `_1`, `_2` suffix
    - Return list of `{"filename", "content_type", "size_bytes", "file_path"}`

3.2. Create `tests/test_extractors.py` — test each function with edge cases (None inputs, encoded subjects, multipart bodies, attachment filtering)

### ~~4. Chat parser~~

4.1. Create `src/mbox_parser/chat.py`:
  - `parse_chat_xml(xml_text: str) -> str` — parse Google Chat XML (`google:archive:conversation` namespace) using `xml.etree.ElementTree`
  - Extract `<cli:message>` elements with `from` attribute and `<cli:body>` text
  - Extract timestamps from `<time ms="..." />` elements
  - Format as readable text: `[timestamp] sender: message` lines
  - Return concatenated body text
  - `is_chat_message(message) -> bool` — check if message has `text/xml` part containing chat namespace

### ~~5. Core parser~~

5.1. Create `src/mbox_parser/parser.py`:
  - `count_messages(mbox_path: Path) -> int` — quick scan counting `From ` lines at start of line for progress bar total (read file in binary, don't parse)
  - `parse_message(message, source_file: str, db: Database, output_dir: Path) -> bool` — extract all fields from one `mailbox.mboxMessage`:
    - Get `Message-ID`, skip if None (malformed)
    - Extract: thread_id (`X-GM-THRID`), in_reply_to, references, from (parseaddr), to/cc/bcc (getaddresses), date, subject (decode), labels, content_type
    - Detect chat: check for `text/xml` with chat namespace → set `is_chat=1`, parse body with `chat.py`
    - Otherwise: extract body with `extract_body()`
    - Insert email into DB, get `email_id` back (None = duplicate, skip attachments)
    - If not duplicate: extract attachments, insert attachment rows, set `has_attachments` flag
    - Wrap in try/except: log warnings on malformed messages, continue
  - `parse_mbox(mbox_path: Path, db: Database, output_dir: Path) -> dict` — main loop:
    - Count messages for progress bar
    - Open `mailbox.mbox(str(mbox_path))`
    - Iterate with `tqdm` progress bar
    - Call `parse_message()` for each
    - Commit every 500 messages
    - Final commit
    - Return stats dict: `{"total", "inserted", "skipped", "errors"}`

### ~~6. CLI~~

6.1. Create `src/mbox_parser/cli.py` with `argparse`:
  - `parse` subcommand:
    - `--mbox-dir PATH` — directory of .mbox files (parse all)
    - `--mbox-file PATH` — single .mbox file
    - `--output-dir PATH` — output directory (default `./output`)
    - `--db PATH` — database path (default `{output-dir}/emails.db`)
    - Validate: must provide one of `--mbox-dir` or `--mbox-file`
    - Create output dir if needed
    - Open DB, create tables
    - Parse each mbox file, print per-file and total stats
  - `stats` subcommand:
    - `--db PATH` — database path (required)
    - Print: total emails, date range, top 10 senders, label distribution, attachment count and total size
  - `main()` function as entry point

6.2. Create `src/mbox_parser/__main__.py` — `from mbox_parser.cli import main; main()`
