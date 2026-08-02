import json
import sys
from mammoth_os.sandbox_runner import run_code

# small project with a single test file
project = {"test_math.py": "def test_dummy():\n    assert 1+1==2\n"}
# test script runs pytest on local files
test_script = "import pytest, sys; sys.exit(pytest.main(['-q']))"

res = None
try:
    res = run_code(code='', test_script=test_script, timeout=120, memory_limit_mb=256, project_files=project)
    # Print JSON result for CI logs
    print(json.dumps(res))
except Exception as e:
    # If run_code itself raised, capture the exception as stderr-equivalent
    res = {"passed": False, "stdout": "", "stderr": f"run_code_exception: {type(e).__name__}: {e}", "returncode": -3}
    print(json.dumps(res))

# Persist the captured runtime stdout and stderr for debugging
try:
    with open('runtime_info.txt', 'w', encoding='utf-8') as _f:
        _f.write(res.get('stdout', '') or '')
except Exception:
    pass
try:
    with open('runtime_error.txt', 'w', encoding='utf-8') as _f:
        _f.write(res.get('stderr', '') or '')
except Exception:
    pass

# Validate that the Docker path was used and tests passed
if res.get('method') != 'docker':
    print('Docker not used by sandbox_runner; got method:', res.get('method'))
    # still write files; exit with code 2 to indicate docker not used
    sys.exit(2)
if not res.get('passed'):
    # tests failed inside sandbox; exit with 1
    sys.exit(1)
# Verify runtime info presence in stdout
out = res.get('stdout', '') or ''
if '---RUNTIME-INFO-START---' not in out or ('Seccomp' not in out and 'CapEff' not in out):
    print('Runtime info missing or seccomp/capability fields not present')
    # ensure an error file is present for the tuner
    try:
        with open('runtime_error.txt', 'a', encoding='utf-8') as _f:
            _f.write('\nRUNTIME-INFO-MISSING')
    except Exception:
        pass
    sys.exit(3)

sys.exit(0)
