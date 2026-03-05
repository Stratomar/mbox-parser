from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.message import Message


CHAT_NAMESPACE = "google:archive:conversation"
NS = {"cli": CHAT_NAMESPACE}


def is_chat_message(message: Message) -> bool:
    for part in message.walk():
        if part.get_content_type() == "text/xml":
            payload = part.get_payload(decode=True)
            if payload and CHAT_NAMESPACE.encode() in payload:  # type: ignore[union-attr]
                return True
    return False


def _get_chat_xml(message: Message) -> str | None:
    for part in message.walk():
        if part.get_content_type() == "text/xml":
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            text = (
                payload.decode("utf-8", errors="replace")
                if isinstance(payload, bytes)
                else str(payload)
            )  # type: ignore[union-attr]
            if CHAT_NAMESPACE in text:
                return text
    return None


def parse_chat_xml(xml_text: str) -> str:
    lines: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return xml_text

    for msg in root.iter(f"{{{CHAT_NAMESPACE}}}message"):
        sender = msg.get("from", "unknown")

        timestamp = ""
        time_el = msg.find(f"{{{CHAT_NAMESPACE}}}time")
        if time_el is not None:
            ms = time_el.get("ms")
            if ms:
                try:
                    dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, OSError):
                    pass

        body_el = msg.find(f"{{{CHAT_NAMESPACE}}}body")
        body = body_el.text if body_el is not None and body_el.text else ""

        if timestamp:
            lines.append(f"[{timestamp}] {sender}: {body}")
        else:
            lines.append(f"{sender}: {body}")

    return "\n".join(lines) if lines else xml_text


def extract_chat_body(message: Message) -> str | None:
    xml_text = _get_chat_xml(message)
    if xml_text is None:
        return None
    return parse_chat_xml(xml_text) or None
