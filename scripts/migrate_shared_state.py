"""Explicit single-record import/export. Stop writers and back up before cutover."""

import argparse
import json
import os
from pathlib import Path

from mammoth_os.shared_state import service_rpc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("import", "export"))
    parser.add_argument("--key", required=True, help="Exact namespaced backend key, e.g. production/notes.json")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--confirm-quiesced", action="store_true")
    args = parser.parse_args()
    if args.direction == "import":
        if not args.confirm_quiesced:
            parser.error("Stop writers and explicitly confirm --confirm-quiesced.")
        payload = json.loads(args.file.read_text(encoding="utf-8"))
        if not isinstance(payload, (dict, list)):
            parser.error("Only JSON object/collection records are supported.")
        result = service_rpc("mammoth_state_cas", {"p_key": args.key, "p_revision": 0, "p_payload": payload})
        if result.get("saved") is not True:
            raise RuntimeError("Import refused: destination already exists. Nothing was overwritten.")
        print("Imported one record at revision 1. Retain the local backup.")
    else:
        result = service_rpc("mammoth_state_read", {"p_key": args.key})
        if not result["revision"]:
            raise RuntimeError("Export refused: source does not exist.")
        with os.fdopen(os.open(args.file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w", encoding="utf-8") as stream:
            json.dump(result["payload"], stream, indent=2)
        print(f"Exported one record at revision {result['revision']}; no existing file was overwritten.")


if __name__ == "__main__":
    main()
