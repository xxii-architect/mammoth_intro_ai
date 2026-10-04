"""Guards for the api_server.py / server_routes/ split."""

import ast
from pathlib import Path

import api_server

ROUTES_DIR = Path(api_server.ROOT) / "server_routes"


def _is_route_def(node: ast.stmt) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    return any(
        isinstance(dec, ast.Call)
        and isinstance(dec.func, ast.Attribute)
        and isinstance(dec.func.value, ast.Name)
        and dec.func.value.id == "app"
        for dec in node.decorator_list
    )


def test_every_fragment_is_loaded():
    on_disk = sorted(path.name for path in ROUTES_DIR.glob("*_routes.py"))
    assert on_disk == sorted(api_server._ROUTE_FRAGMENT_FILES)


def test_fragments_contain_only_route_handlers():
    for name in api_server._ROUTE_FRAGMENT_FILES:
        tree = ast.parse((ROUTES_DIR / name).read_text(encoding="utf-8"))
        stray = [getattr(node, "name", type(node).__name__) for node in tree.body if not _is_route_def(node)]
        assert not stray, f"{name} should only hold @app route handlers; move helpers to api_server.py: {stray}"


def test_api_server_defines_no_routes_itself():
    tree = ast.parse(Path(api_server.__file__).read_text(encoding="utf-8"))
    inline = [node.name for node in tree.body if _is_route_def(node)]
    assert not inline, f"add routes to server_routes/, not api_server.py: {inline}"


def test_route_table_registered_once_and_handlers_exported():
    paths = [(tuple(sorted(getattr(route, "methods", None) or ["WS"])), route.path) for route in api_server.app.routes]
    assert len(paths) == len(set(paths)), "a route fragment was loaded twice"
    api_server._load_route_fragments()
    assert len(api_server.app.routes) == len(paths)
    for handler in ("run_agent", "get_tasks", "atlas_chat", "mammoth_chat", "download_docx_file", "terminal_ws"):
        assert callable(getattr(api_server, handler))
