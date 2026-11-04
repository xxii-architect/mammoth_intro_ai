"""Bounded portable branch export receipts."""

import base64
import binascii
import hashlib
import re
from typing import Any


def decode_branch_export(value: Any, execution_id: str, expected_commit: str) -> bytes:
    if not isinstance(value, dict):
        raise ValueError("Invalid branch export receipt")
    valid = (
        value.get("contract") == "mammoth.owner-branch-export.v1"
        and value.get("execution_id") == execution_id
        and re.fullmatch(r"exec-[a-f0-9]{24}", execution_id) is not None
        and value.get("branch") == f"mammoth/owner/{execution_id}"
        and value.get("filename") == f"{execution_id}.bundle"
        and isinstance(value.get("repo"), str)
        and value.get("commit_sha") == expected_commit
        and re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", expected_commit) is not None
        and isinstance(value.get("base_sha"), str)
        and re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", value["base_sha"]) is not None
        and value.get("requires_base") is True and value.get("automatic_push") is False
        and value.get("encoding") == "base64"
        and type(value.get("size_bytes")) is int and 0 < value["size_bytes"] <= 8 * 1024 * 1024
        and isinstance(value.get("sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]) is not None
        and isinstance(value.get("bundle_base64"), str) and len(value["bundle_base64"]) <= 11_184_812
    )
    if not valid:
        raise ValueError("Invalid branch export receipt")
    try:
        data = base64.b64decode(value["bundle_base64"], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Invalid branch export encoding") from None
    if (len(data) != value["size_bytes"] or not data.startswith((b"# v2 git bundle\n", b"# v3 git bundle\n"))
            or hashlib.sha256(data).hexdigest() != value["sha256"]):
        raise ValueError("Invalid branch export checksum or size")
    return data
