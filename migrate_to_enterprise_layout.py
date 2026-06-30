import os
import shutil
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
BACKUP = ROOT / "_pre_enterprise_backup"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def move_if_exists(src: Path, dst: Path):
    if src.exists():
        ensure_dir(dst.parent)
        print(f"→ Moving {src} -> {dst}")
        shutil.move(str(src), str(dst))


def write_file(path: Path, content: str):
    ensure_dir(path.parent)
    print(f"→ Writing {path}")
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def backup_current_state():
    if BACKUP.exists():
        print("Backup already exists, skipping backup step.")
        return
    print(f"→ Creating backup at {BACKUP}")
    ensure_dir(BACKUP)
    # Minimal backup: pyproject + top-level packages
    for name in ["pyproject.toml", "mammoth_os", "cli"]:
        p = ROOT / name
        if p.exists():
            dst = BACKUP / name
            if p.is_dir():
                shutil.copytree(p, dst)
            else:
                shutil.copy2(p, dst)


def create_enterprise_structure():
    # Core enterprise dirs inside mammoth_os
    for sub in ["core", "engines", "agents", "maintenance", "api"]:
        ensure_dir(SRC / "mammoth_os" / sub)


def rewrite_pyproject():
    pyproject = ROOT / "pyproject.toml"
    content = """
    [project]
    name = "mammoth-os"
    version = "0.1.0"
    description = "Mammoth OS - AI-native learning operating system"
    requires-python = ">=3.10"

    [project.scripts]
    mammoth = "cli.main:main"

    [tool.setuptools]
    package-dir = {"" = "src"}
    packages = ["mammoth_os", "cli"]
    """
    write_file(pyproject, content)


def rewrite_imports():
    # Very minimal: if you had `from mammoth_os import X`, it still works.
    # If you had relative imports, they should still be fine.
    # We’ll just ensure __init__.py files exist.
    for pkg in [
        SRC / "mammoth_os",
        SRC / "mammoth_os" / "core",
        SRC / "mammoth_os" / "engines",
        SRC / "mammoth_os" / "agents",
        SRC / "mammoth_os" / "maintenance",
        SRC / "mammoth_os" / "api",
        SRC / "cli",
    ]:
        init = pkg / "__init__.py"
        if not init.exists():
            write_file(init, "# Package marker\n")


def main():
    print("🐘 Migrating Mammoth OS to enterprise src-layout (with rollback backup)...\n")

    backup_current_state()

    ensure_dir(SRC)
    create_enterprise_structure()

    # Move top-level packages into src/
    move_if_exists(ROOT / "mammoth_os", SRC / "mammoth_os")
    move_if_exists(ROOT / "cli", SRC / "cli")

    rewrite_pyproject()
    rewrite_imports()

    print("\n✅ Migration complete.")
    print(f"Backup of previous layout stored at: {BACKUP}")
    print("Next steps:")
    print("  1) Activate venv if not already: .venv/Scripts/activate")
    print("  2) Run: pip install -e .")
    print("  3) Test: mammoth check (once wired) / python -m cli.main")


if __name__ == "__main__":
    main()
