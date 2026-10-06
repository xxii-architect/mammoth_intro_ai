"""Manifest-derived navigation and hygiene for newly authored course lessons."""
import re


def remove_forward_promises(content: str) -> tuple[str, list[str]]:
    removed = []
    pattern = re.compile(
        r"[^.!?\n]*\b(?:next|upcoming)\s+(?:lesson|session|module)\b[^.!?\n]*(?:[.!?]|$)",
        re.IGNORECASE | re.MULTILINE,
    )

    def drop(match):
        removed.append(match.group(0).strip())
        return ""

    return pattern.sub(drop, content), removed
