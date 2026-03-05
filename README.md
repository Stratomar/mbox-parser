# mbox-parser

A Python tool for parsing mbox email archives.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
python -m mbox_parser
```

## Testing

```bash
make test
```

## Development

```bash
make check   # format + lint + typecheck + test
```
