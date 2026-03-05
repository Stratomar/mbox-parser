import email.header
from email.message import EmailMessage, Message
from pathlib import Path

from mbox_parser.extractors import (
    _sanitize_filename,
    decode_subject,
    extract_attachments,
    extract_body,
    parse_address,
    parse_address_list,
    parse_date,
    parse_labels,
)


class TestParseAddress:
    def test_normal_address(self):
        result = parse_address("John Doe <john@example.com>")
        assert result == {"name": "John Doe", "address": "john@example.com"}

    def test_bare_address(self):
        result = parse_address("john@example.com")
        assert result == {"name": "", "address": "john@example.com"}

    def test_none(self):
        result = parse_address(None)
        assert result == {"name": "", "address": ""}

    def test_empty_string(self):
        result = parse_address("")
        assert result == {"name": "", "address": ""}


class TestParseAddressList:
    def test_multiple_addresses(self):
        result = parse_address_list("Alice <a@x.com>, Bob <b@x.com>")
        assert len(result) == 2
        assert result[0]["address"] == "a@x.com"
        assert result[1]["address"] == "b@x.com"

    def test_none(self):
        assert parse_address_list(None) == []

    def test_empty(self):
        assert parse_address_list("") == []


class TestDecodeSubject:
    def test_plain_subject(self):
        assert decode_subject("Hello World") == "Hello World"

    def test_none(self):
        assert decode_subject(None) == ""

    def test_encoded_utf8(self):
        result = decode_subject("=?UTF-8?Q?Hello_W=C3=B6rld?=")
        assert result == "Hello Wörld"

    def test_encoded_base64(self):
        result = decode_subject("=?UTF-8?B?SGVsbG8gV29ybGQ=?=")
        assert result == "Hello World"


class TestParseDate:
    def test_valid_date(self):
        result = parse_date("Mon, 15 Jan 2024 10:30:00 +0000")
        assert result is not None
        assert result.startswith("2024-01-15")

    def test_none(self):
        assert parse_date(None) is None

    def test_invalid(self):
        assert parse_date("not a date") is None

    def test_empty(self):
        assert parse_date("") is None


class TestParseLabels:
    def test_comma_separated(self):
        result = parse_labels("Inbox, Important, Starred")
        assert result == ["Inbox", "Important", "Starred"]

    def test_none(self):
        assert parse_labels(None) == []

    def test_single(self):
        assert parse_labels("Inbox") == ["Inbox"]

    def test_empty(self):
        assert parse_labels("") == []


class TestExtractBody:
    def test_plain_text_only(self):
        msg = EmailMessage()
        msg.set_content("Hello world")
        text, html = extract_body(msg)
        assert text == "Hello world\n"
        assert html is None

    def test_html_only(self):
        msg = EmailMessage()
        msg.set_content("<p>Hello world</p>", subtype="html")
        text, html = extract_body(msg)
        assert html is not None
        assert "<p>Hello world</p>" in html
        assert text is not None  # converted from html

    def test_multipart_alternative(self):
        msg = EmailMessage()
        msg.make_alternative()
        msg.add_alternative("Plain text body", subtype="plain")
        msg.add_alternative("<p>HTML body</p>", subtype="html")
        text, html = extract_body(msg)
        assert text is not None
        assert html is not None


class TestSanitizeFilename:
    def test_plain_filename_unchanged(self):
        assert _sanitize_filename("report.pdf") == "report.pdf"

    def test_strips_slashes(self):
        assert _sanitize_filename("/CGV_defaut.pdf") == "CGV_defaut.pdf"

    def test_strips_path_components(self):
        assert _sanitize_filename("path/to/file.doc") == "file.doc"

    def test_strips_backslash_path(self):
        assert _sanitize_filename("C:\\Users\\docs\\file.doc") == "file.doc"

    def test_strips_colons_and_newlines(self):
        result = _sanitize_filename("file:name\nwith\rstuff.pdf")
        assert "/" not in result
        assert ":" not in result
        assert "\n" not in result
        assert "\r" not in result

    def test_decodes_mime_encoded(self):
        mime_name = "=?UTF-8?B?ZG9jdW1lbnQucGRm?="  # "document.pdf"
        assert _sanitize_filename(mime_name) == "document.pdf"

    def test_strips_url_query_string(self):
        result = _sanitize_filename("https://example.com/file.pdf?token=abc123")
        assert result == "file.pdf"

    def test_truncates_long_names(self):
        long_name = "a" * 250 + ".pdf"
        result = _sanitize_filename(long_name)
        assert len(result) <= 200
        assert result.endswith(".pdf")

    def test_fallback_on_empty(self):
        result = _sanitize_filename("...")
        assert result.startswith("attachment_")

    def test_strips_null_bytes(self):
        assert "\0" not in _sanitize_filename("file\0name.pdf")


class TestExtractAttachments:
    def test_attachment_saved(self, tmp_path: Path):
        msg = EmailMessage()
        msg.set_content("Body text")
        msg.add_attachment(
            b"PDF content here",
            maintype="application",
            subtype="pdf",
            filename="doc.pdf",
        )

        result = extract_attachments(msg, tmp_path, email_id=1)
        assert len(result) == 1
        assert result[0]["filename"] == "doc.pdf"
        assert result[0]["content_type"] == "application/pdf"
        assert result[0]["size_bytes"] == len(b"PDF content here")
        assert (tmp_path / result[0]["file_path"]).exists()

    def test_skip_ics(self, tmp_path: Path):
        msg = EmailMessage()
        msg.set_content("Body text")
        msg.add_attachment(
            b"BEGIN:VCALENDAR",
            maintype="text",
            subtype="calendar",
            filename="invite.ics",
        )

        result = extract_attachments(msg, tmp_path, email_id=1)
        assert len(result) == 0

    def test_duplicate_filenames(self, tmp_path: Path):
        msg = EmailMessage()
        msg.set_content("Body text")
        msg.add_attachment(
            b"file1 content",
            maintype="application",
            subtype="pdf",
            filename="doc.pdf",
        )
        msg.add_attachment(
            b"file2 content",
            maintype="application",
            subtype="pdf",
            filename="doc.pdf",
        )

        result = extract_attachments(msg, tmp_path, email_id=1)
        assert len(result) == 2
        filenames = {r["filename"] for r in result}
        assert "doc.pdf" in filenames
        assert "doc_1.pdf" in filenames

    def test_header_object_disposition(self, tmp_path: Path):
        """Content-Disposition as a Header object should not cause AttributeError."""
        msg = Message()
        msg["Content-Type"] = "multipart/mixed; boundary=boundary123"
        msg.set_payload([])

        part = Message()
        part["Content-Type"] = "application/pdf"
        # Set Content-Disposition as a Header object (not a plain string)
        part["Content-Disposition"] = email.header.Header(
            'attachment; filename="test.pdf"'
        )
        part.set_payload(b"PDF bytes", "utf-8")
        msg.get_payload().append(part)

        result = extract_attachments(msg, tmp_path, email_id=99)
        assert len(result) == 1
        assert result[0]["filename"] == "test.pdf"

    def test_unsafe_filename_sanitised(self, tmp_path: Path):
        """Filenames with path-illegal characters should be sanitised."""
        msg = EmailMessage()
        msg.set_content("Body text")
        msg.add_attachment(
            b"content",
            maintype="application",
            subtype="pdf",
            filename="/path/to/evil:file.pdf",
        )

        result = extract_attachments(msg, tmp_path, email_id=1)
        assert len(result) == 1
        assert "/" not in result[0]["filename"]
        assert ":" not in result[0]["filename"]
        assert (tmp_path / result[0]["file_path"]).exists()
