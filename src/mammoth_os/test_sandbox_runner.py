def test_sandbox_runner_basic():
    from mammoth_os.sandbox_runner import run_code

    code = """
def add(a, b):
    return a + b
"""
    # test script will import code.py and assert
    test_script = """
import code
res = code.add(2, 3)
assert res == 5
print('TEST_OK')
"""
    result = run_code(code, test_script, timeout=10)
    assert result["passed"] is True, f"Runner failed: stdout={result.get('stdout')} stderr={result.get('stderr')}"
    assert "TEST_OK" in result.get("stdout", "")
