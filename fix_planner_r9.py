#!/usr/bin/env python3
"""
Patch planner_agent.py:
1. Switch _llm_decompose to a few-shot JSON template (like reasoning fix)
2. Add prose fallback that extracts agent mentions + builds synthetic tasks
"""
import ast, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

p = 'src/mammoth_os/agents/planner_agent.py'
src = open(p).read()

# ── 1. New _llm_decompose body ───────────────────────────────────────────────
OLD_FN = '''    async def _llm_decompose(self, goal: str) -> list:
        import json as _j, re as _re, uuid as _uuid
        from mammoth_os.llm_client import get_llm_client
        raw = await get_llm_client().generate(
            f"Break this goal into tasks: {goal}",
            system_prompt=PLANNER_SYSTEM,
            max_tokens=800,
            temperature=0.3,
        )
        try:
            parsed = _j.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        if isinstance(raw, str):
            m = _re.search(r\'\\[.*?"task_id".*?\\]\', raw, _re.DOTALL)
            if m:
                try:
                    return _j.loads(m.group())
                except Exception:
                    pass
        return []'''

NEW_FN = '''    async def _llm_decompose(self, goal: str) -> list:
        import json as _j, re as _re, uuid as _uuid
        from mammoth_os.llm_client import get_llm_client

        # Few-shot template forces the model to fill JSON directly
        template = (
            "Fill the JSON task list below for the GOAL. "
            "Replace ALL placeholder values. Keep exact keys. Output JSON only, no prose.\\n\\n"
            '[{"task_id":"t1","agent":"research","title":"Research the domain","input":{"goal":"understand context"},"depends_on":[],"estimated_minutes":10},'
            '{"task_id":"t2","agent":"brand_voice","title":"Draft campaign messaging","input":{"goal":"create brand copy"},"depends_on":["t1"],"estimated_minutes":20}]'
            "\\n\\nGOAL: " + goal
        )
        raw = await get_llm_client().generate(
            template,
            system_prompt="Output ONLY a JSON array of tasks. No prose. No explanation.",
            max_tokens=900,
            temperature=0.1,
        )

        # Pass 1: direct JSON parse
        if isinstance(raw, str):
            try:
                parsed = _j.loads(raw)
                if isinstance(parsed, list) and parsed:
                    return parsed
            except Exception:
                pass

        # Pass 2: extract JSON array from prose
        if isinstance(raw, str):
            m = _re.search(r\'\\[\\s*\\{[\\s\\S]*?\\}\\s*\\]\', raw)
            if m:
                try:
                    parsed = _j.loads(m.group())
                    if isinstance(parsed, list) and parsed:
                        return parsed
                except Exception:
                    pass

        # Pass 3: prose fallback — extract any agent mentions and synthesise tasks
        if isinstance(raw, str) and raw.strip():
            agent_slugs = [
                "research", "curriculum", "tutor", "coding", "brand_voice",
                "community_engine", "field_ops", "market_intel", "reflection", "mammoth_guide"
            ]
            seen = []
            for slug in agent_slugs:
                if slug.replace("_", " ") in raw.lower() or slug in raw.lower():
                    seen.append(slug)
            if not seen:
                seen = ["research", "brand_voice", "community_engine"]
            tasks = []
            titles = {
                "research": "Research background and context",
                "brand_voice": "Develop brand voice and messaging",
                "community_engine": "Engage and grow the community",
                "field_ops": "Execute field operations",
                "market_intel": "Gather market intelligence",
                "curriculum": "Build educational content",
                "tutor": "Deliver coaching and guidance",
                "coding": "Build technical components",
                "reflection": "Review and iterate on outcomes",
                "mammoth_guide": "Guide platform experience",
            }
            for i, slug in enumerate(seen[:6]):
                tid = f"t{i+1}"
                dep = [f"t{i}"] if i > 0 else []
                tasks.append({
                    "task_id": tid,
                    "agent": slug,
                    "title": titles.get(slug, slug.replace("_", " ").title()),
                    "input": {"goal": goal},
                    "depends_on": dep,
                    "estimated_minutes": 15,
                })
            return tasks

        return []'''

if OLD_FN in src:
    src = src.replace(OLD_FN, NEW_FN, 1)
    try:
        ast.parse(src)
        open(p, 'w').write(src)
        print('OK  planner_agent.py _llm_decompose replaced with few-shot + prose fallback')
    except SyntaxError as e:
        print(f'FAIL: SyntaxError after patch: {e}')
        sys.exit(1)
else:
    # Try to find it differently — show what's there
    idx = src.find('async def _llm_decompose')
    if idx == -1:
        print('FAIL: _llm_decompose not found at all')
    else:
        print('WARN: OLD_FN not matched exactly. Current body:')
        print(repr(src[idx:idx+800]))
    sys.exit(1)

print('Done — run: systemctl restart mammothos')
