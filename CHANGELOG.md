# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Gmail mbox parser with SQLite storage (WAL mode, deduplicated by Message-ID)
- CLI with `parse` and `stats` subcommands
- Attachment extraction to disk with deduplication of filenames
- Google Chat message parsing from embedded XML
- HTML-to-text fallback via html2text
- Gmail label extraction from `X-Gmail-Labels` header
- Threading support via `X-GM-THRID`, `In-Reply-To`, and `References` headers
- Progress bars with tqdm
- Stats command showing top senders, label distribution, date range, and attachment totals
- Initial project scaffold with ruff, mypy, and pytest

### Changed

### Fixed

### Security
