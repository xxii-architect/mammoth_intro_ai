# tests/conftest.py
import os
import sys
import types
import importlib
import pytest  # type: ignore

# Make the tests/ directory importable so "support.fake_supabase" works in CI
_tests_dir = os.path.dirname(__file__)  # tests/
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

# Import the fake factory from tests/support
from support.fake_supabase import fake_get_supabase  # type: ignore

# --- Immediate import-time patch (runs before test collection imports other modules) ---
try:
    sc = importlib.import_module("mammoth_os.supabase_client")
except Exception:
    sc = None

_fake_instance = fake_get_supabase()

if sc is not None:
    try:
        sc.get_supabase = lambda: _fake_instance  # type: ignore
    except Exception:
        pass
    try:
        sc._client_singleton = _fake_instance  # type: ignore
    except Exception:
        pass
    try:
        sc.supabase = _fake_instance  # type: ignore
    except Exception:
        pass

# Replace any already-imported mammoth_os.* module attributes that reference supabase
_replaced_at_import = []
for name, mod in list(sys.modules.items()):
    if not name or not name.startswith("mammoth_os"):
        continue
    if not isinstance(mod, types.ModuleType):
        continue

    if hasattr(mod, "supabase"):
        try:
            old = getattr(mod, "supabase")
            setattr(mod, "supabase", _fake_instance)
            _replaced_at_import.append((name, "supabase", type(old).__name__))
        except Exception:
            pass

    if hasattr(mod, "get_supabase"):
        try:
            old = getattr(mod, "get_supabase")
            setattr(mod, "get_supabase", lambda: _fake_instance)
            _replaced_at_import.append((name, "get_supabase", type(old).__name__))
        except Exception:
            pass

    for attr in ("_client", "client", "_supabase_client", "_client_singleton"):
        if hasattr(mod, attr):
            try:
                old = getattr(mod, attr)
                setattr(mod, attr, _fake_instance)
                _replaced_at_import.append((name, attr, type(old).__name__))
            except Exception:
                pass

if _replaced_at_import:
    print(">>> conftest import-time replaced supabase-like attributes in modules:")
    for r in _replaced_at_import:
        print(">>>   ", r)
else:
    print(">>> conftest import-time found no pre-imported mammoth_os supabase attributes to replace")

# --- Session-scoped fixture (keeps behavior explicit and allows future teardown) ---
@pytest.fixture(scope="session", autouse=True)
def patch_supabase_early():
    """Ensure fake supabase is installed and replace any late-loaded attributes."""
    try:
        sc = importlib.import_module("mammoth_os.supabase_client")
        sc.get_supabase = lambda: _fake_instance  # type: ignore
        sc._client_singleton = _fake_instance  # type: ignore
        sc.supabase = _fake_instance  # type: ignore
    except Exception:
        pass

    replaced = []
    for name, mod in list(sys.modules.items()):
        if not name or not name.startswith("mammoth_os"):
            continue
        if not isinstance(mod, types.ModuleType):
            continue

        if hasattr(mod, "supabase"):
            try:
                old = getattr(mod, "supabase")
                setattr(mod, "supabase", _fake_instance)
                replaced.append((name, "supabase", type(old).__name__))
            except Exception:
                pass

        if hasattr(mod, "get_supabase"):
            try:
                old = getattr(mod, "get_supabase")
                setattr(mod, "get_supabase", lambda: _fake_instance)
                replaced.append((name, "get_supabase", type(old).__name__))
            except Exception:
                pass

        for attr in ("_client", "client", "_supabase_client", "_client_singleton"):
            if hasattr(mod, attr):
                try:
                    old = getattr(mod, attr)
                    setattr(mod, attr, _fake_instance)
                    replaced.append((name, attr, type(old).__name__))
                except Exception:
                    pass

    if replaced:
        print(">>> conftest fixture replaced supabase-like attributes in modules:")
        for r in replaced:
            print(">>>   ", r)
    else:
        print(">>> conftest fixture found no additional mammoth_os attributes to replace")

    yield
