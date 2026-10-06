"""Update only the Mammoth UI site's /api proxy upload limits during deployment."""
import argparse
import re
from pathlib import Path


def configure(text: str, max_bytes: int) -> str:
    pattern = re.compile(r"(location\s+(?:\^~\s+)?/api/?\s*\{)([^{}]*)(\})")
    matches = [match for match in pattern.finditer(text) if re.search(r"\bproxy_pass\s+", match.group(2))]
    if not matches:
        raise ValueError("No simple /api proxy location found. Configure upload limits in this site's API location manually.")
    for match in reversed(matches):
        body = match.group(2)
        def minimum(name, desired, units, body=body):
            found = re.search(r"\b" + name + r"\s+(\d+)([a-zA-Z]*)\s*;", body)
            if not found:
                return desired
            suffix = found.group(2).lower()
            if suffix not in units:
                raise ValueError(f"Unsupported {name} unit; configure this site's limits manually.")
            existing = int(found.group(1)) * units[suffix]
            return 0 if name == "client_max_body_size" and existing == 0 else max(existing, desired)
        size = minimum("client_max_body_size", max_bytes + 1024 * 1024, {"": 1, "k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024})
        read_timeout = minimum("proxy_read_timeout", 120, {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400})
        body_timeout = minimum("client_body_timeout", 120, {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400})
        body = re.sub(r"(?m)^[ \t]*(?:client_max_body_size|proxy_read_timeout|client_body_timeout)\s+[^;]+;[ \t]*(?:\n|$)", "", body).lstrip("\r\n")
        directives = f"\n        client_max_body_size {size};\n        proxy_read_timeout {read_timeout}s;\n        client_body_timeout {body_timeout}s;\n"
        text = text[:match.start()] + match.group(1) + directives + body + match.group(3) + text[match.end():]
    return text


def find_site(dump: str, ui_root: str) -> Path:
    sections = re.split(r"(?m)^# configuration file ([^\n:]+):\s*\n", dump)
    candidates = []
    for index in range(1, len(sections), 2):
        content = sections[index + 1]
        if re.search(r"\broot\s+" + re.escape(ui_root) + r"/?\s*;", content) and re.search(r"\blocation\s+(?:\^~\s+)?/api/?\s*\{", content):
            candidates.append(Path(sections[index]).resolve())
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1:
        raise ValueError("Cannot uniquely identify the Mammoth nginx site. Set MAMMOTH_NGINX_SITE to its configuration path.")
    return candidates[0]


def main():
    import subprocess
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui-root", required=True)
    parser.add_argument("--max-bytes", required=True, type=int)
    parser.add_argument("--site")
    arguments = parser.parse_args()
    if arguments.max_bytes <= 0:
        raise SystemExit("Upload limit must be positive.")
    dump = subprocess.run(["nginx", "-T"], check=True, capture_output=True, text=True).stdout
    site = Path(arguments.site).resolve() if arguments.site else find_site(dump, arguments.ui_root)
    original = site.read_text()
    updated = configure(original, arguments.max_bytes)
    if updated == original:
        print("Mammoth API upload proxy limits already configured.")
        return
    site.write_text(updated)
    try:
        subprocess.run(["nginx", "-t"], check=True)
    except BaseException:
        site.write_text(original)
        raise
    print("Configured Mammoth API upload proxy limits; nginx configuration validated.")


if __name__ == "__main__":
    main()
