# mammoth_os/tests/conftest.py
import os
import sys
import types
import importlib
import pytest  # type: ignore

# Ensure tests/ is importable so "support.fake_supabase" resolves in CI
_tests_dir = os.path.dirname(__file__)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

# Import the fake factory from tests/support
from support.fake_supabase import fake_get_supabase  # type: ignore

# Create a single fake instance to reuse
_fake_instance = fake_get_supabase()

# ---------------------------------------------------------
# HARD PATCH: supabase_client MUST ALWAYS use FakeSupabase
# ---------------------------------------------------------
try:
    sc = importlib.import_module("mammoth_os.supabase_client")

    # Force module-level client
    sc.supabase = _fake_instance# type: ignore
    sc._supabase = _fake_instance# type: ignore

    # Force factory functions
    sc.get_supabase = lambda: _fake_instance# type: ignore
    sc.require_supabase = lambda: _fake_instance# type: ignore

    # Reload to ensure future imports see patched values
    importlib.reload(sc)

except Exception:
    sc = None


# ---------------------------------------------------------
# Patch ANY already-imported mammoth_os modules
# ---------------------------------------------------------
_replaced_at_import = []
for name, mod in list(sys.modules.items()):
    if not name.startswith("mammoth_os"):
        continue
    if not isinstance(mod, types.ModuleType):
        continue

    # Patch module-level supabase
    if hasattr(mod, "supabase"):
        old = getattr(mod, "supabase")
        setattr(mod, "supabase", _fake_instance)
        _replaced_at_import.append((name, "supabase", type(old).__name__))

    # Patch factory functions
    if hasattr(mod, "get_supabase"):
        old = getattr(mod, "get_supabase")
        setattr(mod, "get_supabase", lambda: _fake_instance)
        _replaced_at_import.append((name, "get_supabase", type(old).__name__))

    if hasattr(mod, "require_supabase"):
        old = getattr(mod, "require_supabase")
        setattr(mod, "require_supabase", lambda: _fake_instance)
        _replaced_at_import.append((name, "require_supabase", type(old).__name__))

    # Patch internal client names
    for attr in ("_supabase", "_client", "_client_singleton", "_supabase_client"):
        if hasattr(mod, attr):
            old = getattr(mod, attr)
            setattr(mod, attr, _fake_instance)
            _replaced_at_import.append((name, attr, type(old).__name__))

if _replaced_at_import:
    print(">>> conftest import-time patched supabase attributes:")
    for r in _replaced_at_import:
        print(">>>   ", r)
else:
    print(">>> conftest import-time found no mammoth_os modules to patch")


# ---------------------------------------------------------
# Session fixture: patch modules imported AFTER test collection
# ---------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def patch_supabase_early():
    """
    Ensure FakeSupabase is used for ALL tests, even for modules imported late.
    """

    try:
        sc = importlib.import_module("mammoth_os.supabase_client")

        sc.supabase = _fake_instance# type: ignore
        sc._supabase = _fake_instance# type: ignore
        sc.get_supabase = lambda: _fake_instance# type: ignore
        sc.require_supabase = lambda: _fake_instance# type: ignore

        importlib.reload(sc)

    except Exception:
        sc = None

    replaced = []
    for name, mod in list(sys.modules.items()):
        if not name.startswith("mammoth_os"):
            continue
        if not isinstance(mod, types.ModuleType):
            continue

        if hasattr(mod, "supabase"):
            old = getattr(mod, "supabase")
            setattr(mod, "supabase", _fake_instance)
            replaced.append((name, "supabase", type(old).__name__))

        if hasattr(mod, "get_supabase"):
            old = getattr(mod, "get_supabase")
            setattr(mod, "get_supabase", lambda: _fake_instance)
            replaced.append((name, "get_supabase", type(old).__name__))

        if hasattr(mod, "require_supabase"):
            old = getattr(mod, "require_supabase")
            setattr(mod, "require_supabase", lambda: _fake_instance)
            replaced.append((name, "require_supabase", type(old).__name__))

        for attr in ("_supabase", "_client", "_client_singleton", "_supabase_client"):
            if hasattr(mod, attr):
                old = getattr(mod, attr)
                setattr(mod, attr, _fake_instance)
                replaced.append((name, attr, type(old).__name__))

    if replaced:
        print(">>> conftest fixture patched supabase attributes:")
        for r in replaced:
            print(">>>   ", r)
    else:
        print(">>> conftest fixture found no additional mammoth_os modules to patch")

    yield
