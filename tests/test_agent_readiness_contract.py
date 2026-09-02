import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "src" / "mammoth_os" / "agents"
MAMMOTH_DIR = ROOT / "src" / "mammoth_os"
PLACEHOLDER_MARKERS = (
    "implement later",
    "deeper logic later",
    "stub response",
    "tbd implementation",
)


def _parse_python_file(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _iter_agent_files() -> list[Path]:
    return sorted(
        path
        for path in AGENTS_DIR.glob("*.py")
        if path.name != "__init__.py"
    )


def _iter_engine_files() -> list[Path]:
    return sorted(
        path
        for path in MAMMOTH_DIR.glob("*engine*.py")
        if path.name.endswith(".py")
    )


def test_agent_classes_inherit_base_agent():
    offenders = []
    for path in _iter_agent_files():
        tree = _parse_python_file(path)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("Agent") or node.name == "BaseAgent":
                continue
            inherits_base = any(
                (isinstance(base, ast.Name) and base.id == "BaseAgent")
                or (isinstance(base, ast.Attribute) and base.attr == "BaseAgent")
                for base in node.bases
            )
            if not inherits_base:
                offenders.append(f"{path.name}:{node.name}")

    assert not offenders, f"Agent classes missing BaseAgent inheritance: {offenders}"


def test_agent_classes_have_workflow_entrypoint():
    offenders = []
    for path in _iter_agent_files():
        tree = _parse_python_file(path)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("Agent"):
                continue
            method_names = {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if node.name != "BaseAgent" and "run" not in method_names and "accept_submission" not in method_names:
                offenders.append(f"{path.name}:{node.name}")

    assert not offenders, f"Agent classes missing run/accept_submission entrypoint: {offenders}"


def test_agent_and_engine_sources_have_no_placeholder_markers():
    offenders = []
    for path in [*_iter_agent_files(), *_iter_engine_files()]:
        lowered = path.read_text(encoding="utf-8").lower()
        matches = [marker for marker in PLACEHOLDER_MARKERS if marker in lowered]
        if matches:
            offenders.append(f"{path.name}:{', '.join(matches)}")

    assert not offenders, f"Placeholder markers found in runtime sources: {offenders}"
