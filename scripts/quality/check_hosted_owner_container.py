"""Read-only deployment preflight plus trusted fixtures under the live service UID.

Sent over pinned SSH by the manual production acceptance workflow. This wrapper
does not deploy code, pull images, restart services or alter Docker policies.
"""

import hashlib
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def inspect_host(app_path, reviewed_image, source_revision, probe_b64=""):
    receipt = {
        "contract": "mammoth.hosted-container-evidence.v1",
        "target": "digitalocean_production",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": "not_verified",
        "acceptance_revision": source_revision,
        "scope": "trusted_fixtures_under_live_service_uid_not_tenant_code_certification",
        "deployment_modified": False,
        "images_pulled": False,
    }

    def command(args):
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=15).stdout.strip()

    try:
        root = Path(app_path).resolve(strict=True)
        pid = command(["systemctl", "show", "mammothos", "--property=MainPID", "--value"])
        if not pid.isdigit() or int(pid) < 1:
            raise RuntimeError("live_service_not_found")
        process = Path("/proc") / pid
        if process.stat().st_uid != os.geteuid():
            raise RuntimeError("ssh_uid_does_not_match_live_service_uid")
        if (process / "cwd").resolve() != root:
            raise RuntimeError("live_service_checkout_mismatch")
        receipt["service_uid"] = os.geteuid()
        receipt["deployed_commit"] = command(["git", "-C", str(root), "rev-parse", "HEAD"])
        environment = dict(
            item.decode().split("=", 1) for item in (process / "environ").read_bytes().split(b"\0") if b"=" in item
        )
        image = environment.get("MAMMOTH_OWNER_EXEC_IMAGE", "") if reviewed_image == "configured" else reviewed_image
        if reviewed_image == "configured" and not image and (root / ".env").is_file():
            ticks = int((process / "stat").read_text().rsplit(")", 1)[1].split()[19])
            boot = next(int(line.split()[1]) for line in Path("/proc/stat").read_text().splitlines() if line.startswith("btime "))
            started = boot + ticks / os.sysconf("SC_CLK_TCK")
            if (root / ".env").stat().st_mtime > started:
                raise RuntimeError("image_configuration_changed_since_service_start")
            image = command([
                str(process / "exe"), "-c",
                "import sys;from dotenv import dotenv_values;print(dotenv_values(sys.argv[1]).get('MAMMOTH_OWNER_EXEC_IMAGE') or '')",
                str(root / ".env"),
            ])
            receipt["image_source"] = "unchanged_backend_dotenv"
        else:
            receipt["image_source"] = "live_process_initial_environment" if reviewed_image == "configured" else "explicit_reviewed_digest"
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[a-f0-9]{64}", image):
            raise RuntimeError("reviewed_digest_not_configured")
        receipt["reviewed_image"] = image
        tracked = ["scripts/quality/check_owner_container.py", "src/mammoth_os/owner_execution.py"]
        command(["git", "-C", str(root), "diff", "--exit-code", "HEAD", "--", *tracked])
        receipt["deployed_probe_sha256"] = hashlib.sha256((root / tracked[0]).read_bytes()).hexdigest()
        receipt["deployed_executor_sha256"] = hashlib.sha256((root / tracked[1]).read_bytes()).hexdigest()
        environment["PYTHONPATH"] = str(root / "src")
        with tempfile.TemporaryDirectory(prefix="mammoth-hosted-acceptance-") as directory:
            probe = root / tracked[0]
            if probe_b64:
                if len(probe_b64) > 100000:
                    raise RuntimeError("acceptance_probe_exceeds_bound")
                probe = Path(directory) / "check_owner_container.py"
                probe.write_bytes(base64.b64decode(probe_b64, validate=True))
            receipt["acceptance_probe_sha256"] = hashlib.sha256(probe.read_bytes()).hexdigest()
            receipt["executor_source"] = "deployed_checkout"
            result = subprocess.run(
                [str(process / "exe"), str(probe), "--image", image, "--output-dir", directory],
                cwd=root, env=environment, capture_output=True, text=True, timeout=240,
            )
            path = Path(directory) / "owner_container_evidence.json"
            if not path.is_file():
                raise RuntimeError("deployed_probe_did_not_write_receipt")
            evidence = json.loads(path.read_text())
            receipt["runtime_evidence"] = evidence
            if (result.returncode == 0 and evidence.get("status") == "verified"
                    and evidence.get("contract") == "mammoth.owner-container-evidence.v1"
                    and evidence.get("image") == image
                    and evidence.get("probe_sha256") == receipt["acceptance_probe_sha256"]
                    and evidence.get("executor_sha256") == receipt["deployed_executor_sha256"]):
                receipt["status"] = "verified"
            else:
                receipt["reason"] = "strict_hosted_probe_not_verified"
    except RuntimeError as exc:
        receipt["reason"] = str(exc)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        receipt["reason"] = "hosted_preflight_or_probe_failed"
        receipt["error_type"] = type(exc).__name__
    return receipt


if __name__ == "__main__":
    result = inspect_host(*sys.argv[1:5])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "verified" else 1)
