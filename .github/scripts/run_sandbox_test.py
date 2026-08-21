import json
import sys
from mammoth_os.sandbox_runner import run_code

# small project with a single module
project = {"check_math.py": "VALUE = 2\n"}
# test script imports the project module and asserts expected behavior
test_script = "import check_math; assert check_math.VALUE == 2; print('TEST_OK')"

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

# Validate the probe outcome. This is a diagnostics job, so even a fallback or
# sandbox failure should not fail CI; the artifacts are what we need for tuning.
if res.get('method') != 'docker':
    print('Docker not used by sandbox_runner; got method:', res.get('method'))
    print('Proceeding with captured diagnostics from fallback mode.')

out = res.get('stdout', '') or ''
if '---RUNTIME-INFO-START---' not in out or ('Seccomp' not in out and 'CapEff' not in out):
    print('Runtime info missing or seccomp/capability fields not present')
    try:
        with open('runtime_error.txt', 'a', encoding='utf-8') as _f:
            _f.write('\nRUNTIME-INFO-MISSING')
    except Exception:
        pass

if not res.get('passed'):
    print('Sandbox probe did not pass, but diagnostics were captured for analysis.')

sys.exit(0)
