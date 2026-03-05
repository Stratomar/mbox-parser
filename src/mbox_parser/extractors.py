from __future__ import annotations

import email.header
import email.utils
import re
from email.message import Message
from pathlib import Path

import html2text


def parse_address(header_value: str | None) -> dict[str, str]:
    if not header_value:
        return {"name": "", "address": ""}
    name, addr = email.utils.parseaddr(header_value)
    return {"name": name, "address": addr}


def parse_address_list(header_value: str | None) -> list[dict[str, str]]:
    if not header_value:
        return []
    pairs = email.utils.getaddresses([header_value])
    return [{"name": name, "address": addr} for name, addr in pairs if addr]


def decode_subject(subject: str | email.header.Header | None) -> str:
    if subject is None:
        return ""
    if isinstance(subject, email.header.Header):
        subject = str(subject)
    try:
        decoded_parts = email.header.decode_header(subject)
    except Exception:
        return str(subject)
    parts: list[str] = []
    for data, charset in decoded_parts:
        if isinstance(data, bytes):
            parts.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(data)
    return "".join(parts)


def parse_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        return None


def parse_labels(label_str: str | None) -> list[str]:
    if not label_str:
        return []
    return [label.strip() for label in label_str.split(",") if label.strip()]


def _decode_payload(part: Message) -> str:
    raw = part.get_payload(decode=True)
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    payload: bytes = raw  # type: ignore[assignment]
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset)
    except (UnicodeDecodeError, LookupError):
        return payload.decode("latin-1")


def extract_body(message: Message) -> tuple[str | None, str | None]:
    text_body: str | None = None
    html_body: str | None = None

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and text_body is None:
                text_body = _decode_payload(part)
            elif content_type == "text/html" and html_body is None:
                html_body = _decode_payload(part)
    else:
        content_type = message.get_content_type()
        if content_type == "text/plain":
            text_body = _decode_payload(message)
        elif content_type == "text/html":
            html_body = _decode_payload(message)

    if text_body is None and html_body is not None:
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_tables = True
        h.ignore_emphasis = True
        text_body = h.handle(html_body)

    if text_body:
        text_body = text_body.replace("\r", "")
        text_body = re.sub(r"\n{3,}", "\n\n", text_body)

    return text_body or None, html_body or None


def _safe_filename(filename: str, existing: set[str]) -> str:
    if filename not in existing:
        existing.add(filename)
        return filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = f"{stem}_{counter}{suffix}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate
        counter += 1


def extract_attachments(
    message: Message, output_dir: Path, email_id: int
) -> list[dict[str, str | int]]:
    attachments: list[dict[str, str | int]] = []
    existing_names: set[str] = set()
    attach_dir = output_dir / "attachments" / str(email_id)

    for part in message.walk():
        disposition = part.get("Content-Disposition", "")
        if not disposition:
            continue

        filename = part.get_filename()
        content_type = part.get_content_type()

        is_attachment = "attachment" in disposition.lower()
        is_inline_with_name = "inline" in disposition.lower() and filename

        if not is_attachment and not is_inline_with_name:
            continue

        # Skip junk
        if content_type == "text/calendar" or (filename and filename.endswith(".ics")):
            continue

        raw_payload = part.get_payload(decode=True)
        if raw_payload is None:
            continue
        payload_bytes: bytes = raw_payload  # type: ignore[assignment]

        # Skip small inline images without explicit filename
        if (
            "inline" in disposition.lower()
            and not filename
            and content_type.startswith("image/")
            and len(payload_bytes) < 5120
        ):
            continue

        if not filename:
            continue

        safe_name = _safe_filename(filename, existing_names)
        attach_dir.mkdir(parents=True, exist_ok=True)
        file_path = attach_dir / safe_name
        file_path.write_bytes(payload_bytes)

        attachments.append(
            {
                "filename": safe_name,
                "content_type": content_type,
                "size_bytes": len(payload_bytes),
                "file_path": str(file_path.relative_to(output_dir)),
            }
        )

    return attachments
