#!/usr/bin/env python3
"""
MammothOS Round-9 patch
- Fix 1: planner_agent.py  — broken multi-line regex (binary patch via hex)
- Fix 2: reasoning_agent.py — broaden JSON-extraction regex
- Fix 3: search_agent.py   — confirm LLM fires on zero results
"""
import ast, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # ensure relative paths work

# -----------------------------------------------------------------------------
# Fix 1 — planner_agent.py : replace broken multi-line regex
# -----------------------------------------------------------------------------
p1 = 'src/mammoth_os/agents/planner_agent.py'
raw = open(p1, 'rb').read()

START = b"m = _re.search(r'"
END   = b"', raw, _re.DOTALL)"

idx_s = raw.find(START)
idx_e = raw.find(END, idx_s) if idx_s != -1 else -1

if idx_s != -1 and idx_e != -1:
    end_pos = idx_e + len(END)
    # Build replacement bytes without any backslash-in-string issues
    # Target pattern: \[.*?"task_id".*?\]  (dotall, non-greedy)
    bracket_open  = b'\\['
    bracket_close = b'\\]'
    dot_star      = b'.*?'
    task_id_lit   = b'"task_id"'
    pattern_bytes = bracket_open + dot_star + task_id_lit + dot_star + bracket_close
    # Assemble: m = _re.search(r'...', raw, _re.DOTALL)
    repl = START + pattern_bytes + END
    patched = raw[:idx_s] + repl + raw[end_pos:]
    try:
        ast.parse(patched.decode())
        open(p1, 'wb').write(patched)
        print('OK  Fix 1: planner_agent.py regex repaired')
    except SyntaxError as e:
        print(f'FAIL Fix 1: parse still broken after patch: {e}')
        sys.exit(1)
elif idx_s == -1:
    try:
        ast.parse(raw.decode())
        print('OK  Fix 1: planner_agent.py already parses clean — skipping')
    except SyntaxError as e:
        print(f'FAIL Fix 1: SyntaxError but could not locate regex: {e}')
        sys.exit(1)
else:
    print(f'FAIL Fix 1: found START at {idx_s} but could not find END marker')
    sys.exit(1)

# -----------------------------------------------------------------------------
# Fix 2 — reasoning_agent.py : broaden JSON-extraction regex
# -----------------------------------------------------------------------------
p2 = 'src/mammoth_os/agents/reasoning_agent.py'
t2 = open(p2).read()

# The narrow pattern written by an earlier patch
NARROW = r"""            m = _re2.search(r'\{[\s\S]*?"answer"[\s\S]*?\}', raw)"""
NARROW_OLD = r"""            m = _re2.search(r'\{[^{}]*"answer"[^{}]*\}', raw, _re2.DOTALL)"""

if NARROW in t2:
    print('OK  Fix 2: reasoning_agent.py regex already broadened — skipping')
elif NARROW_OLD in t2:
    t2 = t2.replace(NARROW_OLD, NARROW, 1)
    open(p2, 'w').write(t2)
    print('OK  Fix 2: reasoning_agent.py regex broadened')
else:
    # Show what's actually there
    for i, ln in enumerate(t2.splitlines()):
        if '_re2.search' in ln:
            print(f'  reasoning line {i}: {repr(ln)}')
    print('WARN Fix 2: could not match either known pattern — manual check needed')

# -----------------------------------------------------------------------------
# Fix 3 — search_agent.py : confirm LLM fires on zero results
# -----------------------------------------------------------------------------
p3 = 'src/mammoth_os/agents/search_agent.py'
t3 = open(p3).read()
if 'self._llm_summarize(results or [], query)' in t3:
    print('OK  Fix 3: search_agent.py summarize already patched — skipping')
else:
    OLD_S = 'self._llm_summarize(results, query)'
    NEW_S = 'self._llm_summarize(results or [], query)'
    if OLD_S in t3:
        t3 = t3.replace(OLD_S, NEW_S, 1)
        open(p3, 'w').write(t3)
        print('OK  Fix 3: search_agent.py summarize patched to fire on empty results')
    else:
        print('WARN Fix 3: search_agent.py _llm_summarize call not found')

print('\nAll done — run: systemctl restart mammothos')
