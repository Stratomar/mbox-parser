# mbox-parser

Parse Gmail mbox exports into a deduplicated SQLite database with attachment extraction and Google Chat support.

## Features

- Parses standard mbox files exported from Google Takeout
- Stores emails in a SQLite database, deduplicated by Message-ID
- Extracts and saves attachments to disk
- Handles Google Chat messages embedded as XML
- Converts HTML-only emails to plain text via html2text
- Supports batch processing of multiple mbox files
- Shows progress bars during parsing
- Provides summary statistics (top senders, label distribution, attachment totals)

## Requirements

Python 3.11+

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

Parse a single mbox file:

```
mbox-parser parse --mbox-file ~/Takeout/Mail/All\ mail.mbox
```

Parse all mbox files in a directory:

```
mbox-parser parse --mbox-dir ~/Takeout/Mail/
```

Specify output directory and database path:

```
mbox-parser parse --mbox-dir ~/Takeout/Mail/ --output-dir ./output --db ./emails.db
```

View database statistics:

```
mbox-parser stats --db ./output/emails.db
```

## Output

- **SQLite database** — all email metadata, bodies, labels, and threading info
- **Attachments** — saved to `{output-dir}/attachments/{email-id}/`

## Database Schema

**emails** — one row per message with fields for message ID, thread ID, sender, recipients (to/cc/bcc as JSON), date, subject, body (text and HTML), Gmail labels, and chat flag.

**attachments** — filename, content type, size, and file path linked to the parent email.

## Development

```
make check   # format + lint + typecheck + test
```

Individual targets: `make format`, `make lint`, `make typecheck`, `make test`.
