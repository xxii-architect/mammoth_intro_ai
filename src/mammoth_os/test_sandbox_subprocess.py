import os
from mammoth_os.sandbox_runner import run_code


def test_subprocess_fallback_basic():
    # Force subprocess fallback regardless of Docker availability
    os.environ['FORCE_SUBPROCESS_FALLBACK'] = '1'
    project = {'test_sample.py': 'def test_ok():\n    assert 1 + 1 == 2\n'}
    test_script = "import pytest, sys; sys.exit(pytest.main(['-q']))"
    res = run_code(code='', test_script=test_script, timeout=10, memory_limit_mb=64, project_files=project)
    assert res.get('method') == 'subprocess'
    assert 'passed' in res
    assert res['passed'] is True
    # Clean up env var
    del os.environ['FORCE_SUBPROCESS_FALLBACK']
