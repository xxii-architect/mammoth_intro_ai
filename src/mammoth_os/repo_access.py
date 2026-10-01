"""Repository access policy for Mammoth Mind, ATLAS, and the Workspace SDK.

Rules (enforced server-side, never by UI hiding):

* No repository requested -> no repository context. There is no implicit default.
* The platform repository (the MammothOS checkout the backend runs from) is
  owner/admin-only. Non-admins can never resolve it, by keyword, slug, path,
  or by a fork of it.
* Non-admins may only use repositories they connected themselves. Those are
  cloned into a per-user sandbox directory and are addressed by source id or
  ``owner/repo`` slug, never by raw filesystem path.
* Writes to connected repositories are proposal-only: a local branch + patch
  is produced inside the sandbox clone. Nothing is ever pushed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

GITHUB_SLUG_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
SOURCE_ID_RE = re.compile(r"^src-[a-f0-9]{10}$")
PLATFORM_KEYWORDS = {"platform", "mammothos", "@platform", "mammoth_intro_ai"}
DEFAULT_PLATFORM_SLUGS = {"xxii-architect/mammoth_intro_ai"}
MAX_SOURCES_PER_USER = 5
MAX_CLONE_BYTES = 250 * 1024 * 1024
CLONE_TIMEOUT_S = 180

SCOPE_NONE = "none"
SCOPE_PLATFORM = "platform"
SCOPE_TENANT = "tenant"
SCOPE_LOCAL_PATH = "local_path"
SCOPE_DENIED = "denied"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def user_storage_key(user_id: str) -> str:
    """Stable, filesystem-safe key for a user id (never the raw id)."""
    return hashlib.sha256(str(user_id or "anonymous").encode("utf-8")).hexdigest()[:20]


def normalize_slug(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://(www\.)?github\.com/", "", text, flags=re.I)
    text = re.sub(r"\.git$", "", text).strip("/")
    if not GITHUB_SLUG_RE.fullmatch(text):
        return ""
    owner, repo = text.split("/", 1)
    if repo in {".", ".."}:
        return ""
    return f"{owner}/{repo}"


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


@dataclass
class RepoResolution:
    root: str = ""
    scope: str = SCOPE_NONE
    requested_root: str = ""
    root_warning: str = ""
    source_id: str = ""
    slug: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.root) and self.scope in {SCOPE_PLATFORM, SCOPE_TENANT, SCOPE_LOCAL_PATH}

    def as_dict(self) -> Dict[str, str]:
        return {
            "root": self.root,
            "scope": self.scope,
            "requested_root": self.requested_root,
            "root_warning": self.root_warning,
            "source_id": self.source_id,
            "slug": self.slug,
        }


@dataclass
class RepoAccessPolicy:
    platform_root: Path
    tenant_base: Path
    registry_dir: Path
    platform_slugs: set = field(default_factory=lambda: set(DEFAULT_PLATFORM_SLUGS))
    github_api: str = "https://api.github.com"

    @classmethod
    def from_env(cls, platform_root: Path, state_dir: Path) -> "RepoAccessPolicy":
        slugs = {s.lower() for s in DEFAULT_PLATFORM_SLUGS}
        for item in str(os.environ.get("MAMMOTH_PLATFORM_REPOS", "")).split(","):
            slug = normalize_slug(item)
            if slug:
                slugs.add(slug.lower())
        tenant_base = Path(os.environ.get("MAMMOTH_TENANT_REPO_DIR") or (state_dir / "tenant_repos"))
        return cls(
            platform_root=Path(platform_root),
            tenant_base=tenant_base,
            registry_dir=state_dir / "repo_sources",
            platform_slugs=slugs,
        )

    # ── registry ────────────────────────────────────────────────────────────
    def _registry_path(self, user_id: str) -> Path:
        return self.registry_dir / f"{user_storage_key(user_id)}.json"

    def user_sandbox_dir(self, user_id: str) -> Path:
        return self.tenant_base / user_storage_key(user_id)

    def list_sources(self, user_id: str) -> List[Dict[str, Any]]:
        path = self._registry_path(user_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def _save_sources(self, user_id: str, sources: List[Dict[str, Any]]) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        path = self._registry_path(user_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(sources, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def public_source(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """Source view safe to return to clients (no server paths)."""
        return {k: source.get(k) for k in ("id", "slug", "provider", "default_branch", "status", "added_at", "last_synced_at", "error")}

    def find_source(self, user_id: str, ref: str) -> Optional[Dict[str, Any]]:
        ref = str(ref or "").strip()
        slug = normalize_slug(ref).lower()
        for source in self.list_sources(user_id):
            if source.get("id") == ref or (slug and str(source.get("slug") or "").lower() == slug):
                return source
        return None

    def source_path(self, user_id: str, source: Dict[str, Any]) -> Optional[Path]:
        sandbox = self.user_sandbox_dir(user_id)
        candidate = sandbox / str(source.get("id") or "")
        if not SOURCE_ID_RE.fullmatch(str(source.get("id") or "")):
            return None
        if not is_within(candidate, sandbox) or not candidate.is_dir():
            return None
        return candidate

    def is_platform_slug(self, slug: str) -> bool:
        return bool(slug) and slug.lower() in self.platform_slugs

    # ── resolution ──────────────────────────────────────────────────────────
    def resolve(self, raw_root: Any, *, user_id: str, is_admin: bool) -> RepoResolution:
        requested = str(raw_root or "").strip()
        if not requested:
            return RepoResolution()
        if len(requested) >= 400:
            return RepoResolution(scope=SCOPE_DENIED, requested_root=requested[:400], root_warning="Requested repository reference is too long.")

        lowered = requested.lower()
        slug = normalize_slug(requested)

        if lowered in PLATFORM_KEYWORDS or self.is_platform_slug(slug):
            if is_admin:
                return RepoResolution(root=str(self.platform_root), scope=SCOPE_PLATFORM, requested_root=requested, slug=slug)
            return RepoResolution(scope=SCOPE_DENIED, requested_root=requested, root_warning="That repository is private to the MammothOS owner. Connect your own repository to use repo context.")

        if SOURCE_ID_RE.fullmatch(requested) or slug:
            source = self.find_source(user_id, requested)
            if source is None:
                return RepoResolution(scope=SCOPE_DENIED, requested_root=requested, root_warning="Repository not connected. Add it under Repo Sources first.")
            path = self.source_path(user_id, source)
            if path is None:
                return RepoResolution(scope=SCOPE_DENIED, requested_root=requested, root_warning="Connected repository is not synced yet. Run a sync and try again.")
            return RepoResolution(root=str(path), scope=SCOPE_TENANT, requested_root=requested, source_id=str(source.get("id")), slug=str(source.get("slug") or ""))

        if not is_admin:
            return RepoResolution(scope=SCOPE_DENIED, requested_root=requested, root_warning="Filesystem paths are owner-only. Connect a GitHub repository instead.")

        candidate = Path(requested)
        if candidate.is_absolute() and candidate.is_dir():
            scope = SCOPE_PLATFORM if is_within(candidate, self.platform_root) and is_within(self.platform_root, candidate) else SCOPE_LOCAL_PATH
            return RepoResolution(root=str(candidate), scope=scope, requested_root=requested)
        return RepoResolution(scope=SCOPE_DENIED, requested_root=requested, root_warning="Requested repository path was not found on the backend host.")

    # ── connect / sync / remove ─────────────────────────────────────────────
    def _git(self, args: List[str], *, cwd: Optional[Path] = None, timeout: int = 60) -> Dict[str, Any]:
        env = dict(os.environ)
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "GCM_INTERACTIVE": "never",
            "GIT_CONFIG_NOSYSTEM": "1",
        })
        cmd = ["git", "-c", "core.symlinks=false", "-c", "core.hooksPath=" + os.devnull, "-c", "protocol.file.allow=never", *args]
        try:
            proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout, env=env)
            return {"ok": proc.returncode == 0, "stdout": proc.stdout or "", "stderr": (proc.stderr or "")[-1200:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": f"git timed out after {timeout}s"}
        except Exception as exc:  # pragma: no cover - environment specific
            return {"ok": False, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}

    def _github_repo_meta(self, slug: str) -> Dict[str, Any]:
        req = urllib.request.Request(f"{self.github_api}/repos/{slug}", headers={"Accept": "application/vnd.github+json", "User-Agent": "MammothOS-RepoAccess"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310 - fixed https host
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return {"_error": f"http_{exc.code}"}
        except Exception as exc:
            return {"_error": type(exc).__name__}

    def _is_platform_fork(self, meta: Dict[str, Any]) -> bool:
        for key in ("parent", "source"):
            parent = meta.get(key)
            if isinstance(parent, dict) and self.is_platform_slug(str(parent.get("full_name") or "")):
                return True
        return self.is_platform_slug(str(meta.get("full_name") or ""))

    def connect(self, user_id: str, raw_slug: Any, *, is_admin: bool) -> Dict[str, Any]:
        slug = normalize_slug(raw_slug)
        if not slug:
            return {"status": "error", "code": "invalid_repo", "error": "Use a GitHub repository in owner/repo form."}
        if self.is_platform_slug(slug) and not is_admin:
            return {"status": "error", "code": "platform_repo_private", "error": "That repository is private to the MammothOS owner."}
        sources = self.list_sources(user_id)
        existing = self.find_source(user_id, slug)
        if existing:
            return {"status": "ok", "source": self.public_source(existing), "already_connected": True}
        if len(sources) >= MAX_SOURCES_PER_USER:
            return {"status": "error", "code": "limit_reached", "error": f"You can connect up to {MAX_SOURCES_PER_USER} repositories."}

        meta = self._github_repo_meta(slug)
        if not is_admin and not meta.get("_error") and self._is_platform_fork(meta):
            return {"status": "error", "code": "platform_repo_private", "error": "Forks of the MammothOS platform repository cannot be connected."}
        if meta.get("private") is True:
            return {"status": "error", "code": "private_repo_unsupported", "error": "Private repositories need the MammothOS GitHub App (coming soon). Public repositories work today."}

        source = {
            "id": f"src-{uuid.uuid4().hex[:10]}",
            "slug": str(meta.get("full_name") or slug) if not meta.get("_error") else slug,
            "provider": "github",
            "default_branch": str(meta.get("default_branch") or "main") if not meta.get("_error") else "",
            "status": "pending",
            "added_at": _utc_now(),
            "last_synced_at": "",
            "error": "",
        }
        sources.append(source)
        self._save_sources(user_id, sources)
        synced = self.sync(user_id, source["id"])
        return synced if synced.get("status") != "ok" else {"status": "ok", "source": synced["source"]}

    def _update_source(self, user_id: str, source_id: str, **changes: Any) -> Optional[Dict[str, Any]]:
        sources = self.list_sources(user_id)
        updated = None
        for item in sources:
            if item.get("id") == source_id:
                item.update(changes)
                updated = item
        if updated is not None:
            self._save_sources(user_id, sources)
        return updated

    @staticmethod
    def _dir_size(path: Path) -> int:
        total = 0
        for item in path.rglob("*"):
            try:
                if item.is_file() and not item.is_symlink():
                    total += item.stat().st_size
            except OSError:
                continue
        return total

    def sync(self, user_id: str, source_id: str) -> Dict[str, Any]:
        source = self.find_source(user_id, source_id)
        if source is None or not SOURCE_ID_RE.fullmatch(str(source.get("id") or "")):
            return {"status": "error", "code": "not_found", "error": "Repository source not found."}
        sandbox = self.user_sandbox_dir(user_id)
        sandbox.mkdir(parents=True, exist_ok=True)
        dest = sandbox / source["id"]
        if not is_within(dest, sandbox):
            return {"status": "error", "code": "invalid_path", "error": "Invalid sandbox path."}
        url = f"https://github.com/{source['slug']}.git"
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        args = ["clone", "--depth", "1", "--no-tags", "--single-branch"]
        if source.get("default_branch"):
            args += ["--branch", str(source["default_branch"])]
        result = self._git([*args, url, str(dest)], timeout=CLONE_TIMEOUT_S)
        if not result["ok"]:
            shutil.rmtree(dest, ignore_errors=True)
            updated = self._update_source(user_id, source["id"], status="error", error="Clone failed. Check that the repository exists and is public.")
            return {"status": "error", "code": "clone_failed", "error": "Clone failed. Check that the repository exists and is public.", "source": self.public_source(updated or source)}
        if self._dir_size(dest) > MAX_CLONE_BYTES:
            shutil.rmtree(dest, ignore_errors=True)
            updated = self._update_source(user_id, source["id"], status="error", error="Repository exceeds the sandbox size limit.")
            return {"status": "error", "code": "too_large", "error": "Repository exceeds the sandbox size limit.", "source": self.public_source(updated or source)}
        branch = self._git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=dest)
        updated = self._update_source(
            user_id,
            source["id"],
            status="ready",
            error="",
            last_synced_at=_utc_now(),
            default_branch=(branch["stdout"].strip() if branch["ok"] else source.get("default_branch")) or "main",
        )
        return {"status": "ok", "source": self.public_source(updated or source)}

    def remove(self, user_id: str, source_id: str) -> Dict[str, Any]:
        source = self.find_source(user_id, source_id)
        if source is None:
            return {"status": "error", "code": "not_found", "error": "Repository source not found."}
        path = self.source_path(user_id, source)
        if path is not None:
            shutil.rmtree(path, ignore_errors=True)
        self._save_sources(user_id, [s for s in self.list_sources(user_id) if s.get("id") != source.get("id")])
        return {"status": "ok", "removed": source.get("id")}

    # ── proposal-only writes ────────────────────────────────────────────────
    def propose_patch(self, user_id: str, source_id: str, changes: List[Dict[str, Any]], *, title: str = "") -> Dict[str, Any]:
        """Apply file changes on a fresh local branch and return a git patch.

        Nothing is pushed. The sandbox is reset to the default branch afterwards
        so read context stays clean.
        """
        source = self.find_source(user_id, source_id)
        if source is None:
            return {"status": "error", "code": "not_found", "error": "Repository source not found."}
        repo = self.source_path(user_id, source)
        if repo is None:
            return {"status": "error", "code": "not_synced", "error": "Repository is not synced."}
        if not isinstance(changes, list) or not changes or len(changes) > 20:
            return {"status": "error", "code": "invalid_changes", "error": "Provide 1-20 file changes."}

        prepared: List[tuple] = []
        for change in changes:
            rel = str((change or {}).get("path") or "").replace("\\", "/").strip().lstrip("/")
            content = (change or {}).get("content")
            if not rel or ".." in rel.split("/") or rel.startswith(".git/") or rel == ".git" or not isinstance(content, str):
                return {"status": "error", "code": "invalid_path", "error": f"Invalid change path: {rel or '(empty)'}"}
            if len(content) > 400_000:
                return {"status": "error", "code": "too_large", "error": f"Change too large: {rel}"}
            target = repo / rel
            if not is_within(target, repo) or (target.exists() and target.is_symlink()):
                return {"status": "error", "code": "invalid_path", "error": f"Invalid change path: {rel}"}
            prepared.append((rel, target, content))

        default_branch = str(source.get("default_branch") or "main")
        branch = f"mammoth/proposal-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        if not self._git(["checkout", "-q", "-b", branch], cwd=repo)["ok"]:
            return {"status": "error", "code": "git_error", "error": "Could not create proposal branch."}
        try:
            for _, target, content in prepared:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            self._git(["add", "--", *[rel for rel, _, _ in prepared]], cwd=repo)
            message = (title or "MammothOS proposal").strip()[:120]
            commit = self._git(
                ["-c", "user.name=MammothOS Agent", "-c", "user.email=agent@mammothos.invalid", "commit", "-q", "--no-verify", "-m", message],
                cwd=repo,
            )
            if not commit["ok"]:
                return {"status": "error", "code": "no_changes", "error": "No changes to propose."}
            patch = self._git(["format-patch", "-1", "--stdout"], cwd=repo)
            stat = self._git(["show", "--stat", "--format=", "HEAD"], cwd=repo)
            return {
                "status": "ok",
                "branch": branch,
                "patch": patch["stdout"][:600_000],
                "stat": stat["stdout"].strip(),
                "pushed": False,
                "next_step": "Apply with `git am` in your clone, or open a pull request from the patch. MammothOS never pushes to your repository.",
            }
        finally:
            self._git(["checkout", "-q", "-f", default_branch], cwd=repo)
