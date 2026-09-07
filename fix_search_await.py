# Fix search_agent.py: summarize() must await _llm_summarize, not call _run_async
p = 'src/mammoth_os/agents/search_agent.py'
t = open(p).read()
OLD = '        llm_sum = self._run_async(self._llm_summarize(results or [], query))'
NEW = '        llm_sum = await self._llm_summarize(results or [], query)'
if OLD in t:
    open(p, 'w').write(t.replace(OLD, NEW, 1))
    print('OK  search summarize: _run_async -> await')
elif NEW in t:
    print('OK  already uses await — skipping')
else:
    print('WARN: neither form found')
    for i, ln in enumerate(t.splitlines()):
        if '_llm_summarize' in ln and 'def' not in ln:
            print(f'  line {i}: {repr(ln)}')
