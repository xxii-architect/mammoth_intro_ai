#!/usr/bin/env python3
"""
Fix api_server.py planner dispatch block:
1. Add await before _pa.run() — it's async
2. Unwrap tasks from plan dict into output top-level
"""
import ast, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

p = 'api_server.py'
src = open(p).read()

# ── Fix 1: add await ──────────────────────────────────────────────────────────
OLD_RUN = '                _pa_result = _pa.run(_pa_payload)'
NEW_RUN = '                _pa_result = await _pa.run(_pa_payload)'

if NEW_RUN in src:
    print('OK  await already present — skipping Fix 1')
elif OLD_RUN in src:
    src = src.replace(OLD_RUN, NEW_RUN, 1)
    print('OK  Fix 1: await added to _pa.run()')
else:
    print('WARN Fix 1: _pa.run line not found')
    for i, ln in enumerate(src.splitlines()):
        if '_pa.run' in ln:
            print(f'  line {i}: {repr(ln)}')

# ── Fix 2: expose tasks at output top level ───────────────────────────────────
OLD_OUT = (
    '                result = {\n'
    '                    "status": _pa_result.get("status", "ok"),\n'
    '                    "runtime_agent": "planner",\n'
    '                    "output": _pa_result,\n'
    '                }'
)
NEW_OUT = (
    '                _pa_tasks = _pa_result.get("tasks") or _pa_result.get("plan", {}).get("tasks") or []\n'
    '                result = {\n'
    '                    "status": _pa_result.get("status", "ok"),\n'
    '                    "runtime_agent": "planner",\n'
    '                    "output": {**�pa_result, "tasks": _pa_tasks},\n'
    '                }'
)

if '_pa_tasks' in src:
    print('OK  tasks unwrap already present — skipping Fix 2')
elif OLD_OUT in src:
    src = src.replace(OLD_OUT, NEW_OUT, 1)
    print('OK  Fix 2: tasks unwrapped from plan dict')
else:
    print('WARN Fix 2: output block not found')
    for i, ln in enumerate(src.splitlines()):
        if '"runtime_agent": "planner"' in ln:
            print(f'  line {i}: {repr(ln)}')

# ── Verify parse + write ──────────────────────────────────────────────────────
try:
    ast.parse(src)
    open(p, 'w').write(src)
    print('OK  api_server.py written — parse clean')
except SyntaxError as e:
    print(f'FAIL: SyntaxError after patch: {e}')
    sys.exit(1)

print('Done — run: systemctl restart mammothos')
