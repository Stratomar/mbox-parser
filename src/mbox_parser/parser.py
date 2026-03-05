from __future__ import annotations

import logging
import mailbox
from pathlib import Path

from tqdm import tqdm

from mbox_parser.chat import extract_chat_body, is_chat_message
from mbox_parser.db import Database
from mbox_parser.extractors import (
    decode_subject,
    extract_attachments,
    extract_body,
    parse_address,
    parse_address_list,
    parse_date,
    parse_labels,
)

logger = logging.getLogger(__name__)

COMMIT_INTERVAL = 500


def count_messages(mbox_path: Path) -> int:
    count = 0
    with open(mbox_path, "rb") as f:
        for line in f:
            if line.startswith(b"From "):
                count += 1
    return count


def parse_message(
    message: mailbox.mboxMessage,
    source_file: str,
    db: Database,
    output_dir: Path,
) -> bool:
    message_id = message.get("Message-ID")
    if not message_id:
        return False

    thread_id = message.get("X-GM-THRID")
    in_reply_to = message.get("In-Reply-To")
    references = message.get("References")

    sender = parse_address(message.get("From"))
    to_addresses = parse_address_list(message.get("To"))
    cc_addresses = parse_address_list(message.get("Cc"))
    bcc_addresses = parse_address_list(message.get("Bcc"))

    date = parse_date(message.get("Date"))
    subject = decode_subject(message.get("Subject"))
    labels = parse_labels(message.get("X-Gmail-Labels"))
    content_type = message.get_content_type()

    is_chat = is_chat_message(message)

    if is_chat:
        body_text = extract_chat_body(message)
        body_html = None
    else:
        body_text, body_html = extract_body(message)

    data = {
        "message_id": message_id,
        "thread_id": thread_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "from_name": sender["name"],
        "from_address": sender["address"],
        "to_addresses": to_addresses,
        "cc_addresses": cc_addresses,
        "bcc_addresses": bcc_addresses,
        "date": date,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "labels": labels,
        "source_file": source_file,
        "content_type": content_type,
        "is_chat": 1 if is_chat else 0,
        "has_attachments": 0,
    }

    email_id = db.insert_email(data)
    if email_id is None:
        return False

    if not is_chat:
        attachments = extract_attachments(message, output_dir, email_id)
        if attachments:
            for att in attachments:
                att["email_id"] = email_id
                db.insert_attachment(att)
            db.update_has_attachments(email_id)

    return True


def parse_mbox(
    mbox_path: Path,
    db: Database,
    output_dir: Path,
) -> dict[str, int]:
    source_file = mbox_path.name
    total = count_messages(mbox_path)

    mbox = mailbox.mbox(str(mbox_path))

    stats = {"total": 0, "inserted": 0, "skipped": 0, "errors": 0}

    for message in tqdm(mbox, total=total, desc=source_file, unit="msg"):
        stats["total"] += 1
        try:
            inserted = parse_message(message, source_file, db, output_dir)
            if inserted:
                stats["inserted"] += 1
            else:
                stats["skipped"] += 1
        except Exception:
            logger.warning(
                "Error parsing message %d in %s",
                stats["total"],
                source_file,
                exc_info=True,
            )
            stats["errors"] += 1

        if stats["total"] % COMMIT_INTERVAL == 0:
            db.commit()

    db.commit()
    return stats
