import asyncio

import api_server
import mammoth_os.llm_client as llm_client_mod


class DummyClient:
    def __init__(self, prompt_log):
        self.prompt_log = prompt_log
        self.model = 'dummy-model'

    async def generate(self, prompt: str, **kwargs) -> str:
        self.prompt_log.append(prompt)
        return 'native-chat-response'


def test_mammoth_chat_assistant_uses_separate_history(monkeypatch):
    prompt_log = []
    state = {}

    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(llm_client_mod, 'get_llm_client', lambda config=None: DummyClient(prompt_log))

    response = asyncio.run(
        api_server.mammoth_chat(
            {
                'message': 'Help me plan the next MammothOS milestone.',
                'agent_id': 'assistant',
                'mode': 'chat',
                'page_context': {'current_page': 'chat'},
            }
        )
    )

    assert response['status'] == 'ok'
    assert response['reply'] == 'native-chat-response'
    assert state.get('mammoth_chat_history')
    assert 'assistant_chat_history' not in state
    assert prompt_log and 'MammothOS Chat' in prompt_log[-1]
    assert any(step['label'] == 'Priming mammoth cores' for step in response['thought_steps'])


def test_mammoth_chat_preserves_other_user_history(monkeypatch):
    prompt_log = []
    state = {
        'mammoth_chat_history': [
            {'role': 'assistant', 'message': 'keep me', 'user_id': 'other-user', 'account_id': 'default'},
        ]
    }

    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(api_server, '_current_request_user_id', lambda: 'current-user')
    monkeypatch.setattr(api_server, '_active_account_id', lambda payload: 'default')
    monkeypatch.setattr(llm_client_mod, 'get_llm_client', lambda config=None: DummyClient(prompt_log))

    response = asyncio.run(
        api_server.mammoth_chat(
            {
                'message': 'Scoped response please',
                'agent_id': 'assistant',
                'mode': 'chat',
            }
        )
    )

    assert response['status'] == 'ok'
    assert all(item.get('user_id') == 'current-user' for item in response['chat_history'])
    assert any(item.get('user_id') == 'other-user' for item in state.get('mammoth_chat_history', []))


def test_mammoth_chat_dispatches_to_agent_runtime(monkeypatch):
    state = {}

    async def fake_run_agent(body):
        return {
            'status': 'ok',
            'result': {
                'status': 'ok',
                'output': {'summary': 'Patched files successfully.'},
            },
            'agent_id': body.get('agent_id'),
            'task_id': 'task-1234',
            'thought_steps': [
                {'label': 'Routing decision', 'detail': 'runtime_agent=coding', 'status': 'info'},
                {'label': 'Run complete', 'detail': 'task_status=completed', 'status': 'success'},
            ],
        }

    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(api_server, 'run_agent', fake_run_agent)

    response = asyncio.run(
        api_server.mammoth_chat(
            {
                'message': 'Patch the agent page to improve status UX.',
                'agent_id': 'coding_agent',
                'coding_intent': 'patch_existing',
                'mode': 'chat',
            }
        )
    )

    assert response['status'] == 'ok'
    assert response['dispatched'] is True
    assert response['task_id'] == 'task-1234'
    assert response['reply'] == 'Patched files successfully.'
    assert any(step['label'] == 'Routing decision' for step in response['thought_steps'])


def test_mammoth_chat_guide_preserves_steps_from_nested_agent_output(monkeypatch):
    state = {}

    async def fake_run_agent(body):
        return {
            'status': 'ok',
            'result': {
                'status': 'error',
                'output': {
                    'message': '**MammothOS Guide** mock',
                    'guide_steps': [
                        {'title': 'Step 1', 'detail': 'Mock detail', 'kind': 'info'},
                        {'title': 'Step 2', 'detail': 'Mock detail 2', 'kind': 'tip'},
                    ],
                    'branch': 'main',
                    'adapter': 'mammoth-guide',
                },
            },
            'agent_id': body.get('agent_id'),
            'task_id': 'task-guide-1',
            'thought_steps': [
                {'label': 'Routing decision', 'detail': 'runtime_agent=mammoth_guide', 'status': 'info'},
                {'label': 'Run complete', 'detail': 'task_status=failed', 'status': 'warning'},
            ],
        }

    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(api_server, 'run_agent', fake_run_agent)

    response = asyncio.run(
        api_server.mammoth_chat(
            {
                'message': 'Guide me through MammothOS',
                'agent_id': 'mammoth_guide',
                'mode': 'chat',
                'repo_context': {'root': '/repo', 'branch': 'main'},
            }
        )
    )

    assert response['status'] == 'ok'
    assert response['reply'] == '**MammothOS Guide** mock'
    assert isinstance(response.get('guide_steps'), list)
    assert len(response['guide_steps']) == 2
    assert response.get('guide_branch') == 'main'
    assert isinstance(response['chat_history'][-1].get('guide_steps'), list)
    assert response['chat_history'][-1]['guide_steps'][0]['title'] == 'Step 1'


def test_mammoth_chat_stream_emits_sse_events(monkeypatch):
    state = {}

    async def fake_chat(body):
        return {
            'status': 'ok',
            'reply': 'streamed response text',
            'chat_history': [
                {'role': 'user', 'message': body['message']},
                {'role': 'assistant', 'message': 'streamed response text'},
            ],
            'thought_steps': [
                {'ts': '2026-08-17T23:00:00Z', 'label': 'Consulting the herd', 'detail': 'Running native MammothOS assistant response', 'status': 'info'},
                {'ts': '2026-08-17T23:00:01Z', 'label': 'Tusks charged', 'detail': 'adapter=openai model=gpt-4o-mini', 'status': 'success'},
            ],
            'agent_id': 'assistant',
            'adapter': 'openai',
            'model': 'gpt-4o-mini',
            'mode': 'chat',
            'task_id': 'task-1234',
            'dispatched': False,
        }

    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(api_server, 'mammoth_chat', fake_chat)

    response = asyncio.run(api_server.mammoth_chat_stream({'message': 'stream this', 'agent_id': 'assistant'}))
    assert getattr(response, 'media_type', '') == 'text/event-stream'

    async def collect():
        payload = []
        async for chunk in response.body_iterator:
            payload.append(chunk.decode('utf-8') if isinstance(chunk, (bytes, bytearray)) else str(chunk))
        return ''.join(payload)

    body = asyncio.run(collect())
    assert 'event: meta' in body
    assert 'event: thought' in body
    assert 'event: chunk' in body
    assert 'event: done' in body


def test_parse_mammoth_chat_command_internet_variants():
    assert api_server._parse_mammoth_chat_command('/web https://example.com')['kind'] == 'web'
    assert api_server._parse_mammoth_chat_command('/research runtime fallback handling')['kind'] == 'research'
    assert api_server._parse_mammoth_chat_command('/commit chore: test')['operation'] == 'git_commit'
    assert api_server._parse_mammoth_chat_command('/push origin main')['operation'] == 'git_push'
    assert api_server._parse_mammoth_chat_command('/web')['kind'] == 'error'


def test_mammoth_chat_web_command_uses_internet_tool(monkeypatch):
    state = {}

    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(
        api_server,
        '_run_internet_command',
        lambda slash: {
            'status': 'ok',
            'reply': 'Web summary for https://example.com',
            'evidence': {'source': 'internet', 'kind': slash.get('kind')},
        },
    )

    response = asyncio.run(
        api_server.mammoth_chat(
            {
                'message': '/web https://example.com',
                'agent_id': 'assistant',
                'mode': 'chat',
            }
        )
    )

    assert response['status'] == 'ok'
    assert response['adapter'] == 'internet-tool'
    assert response['reply'].startswith('Web summary')
    assert response['chat_history'][-1]['adapter'] == 'internet-tool'


def test_atlas_chat_research_command_uses_internet_tool(monkeypatch):
    state = {}

    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(
        api_server,
        '_run_internet_command',
        lambda slash: {
            'status': 'ok',
            'reply': 'Internet research brief for: mammoth os',
            'evidence': {'source': 'internet', 'kind': slash.get('kind')},
        },
    )

    response = asyncio.run(
        api_server.atlas_chat(
            {
                'message': '/research mammoth os',
                'mode': 'assistant',
                'page_context': {'current_page': 'atlas'},
            }
        )
    )

    assert response['status'] == 'ok'
    assert response['adapter'] == 'internet-tool'
    assert 'research brief' in response['reply']
    assert response['chat_history'][-1]['adapter'] == 'internet-tool'


def test_mammoth_chat_gitops_is_disabled_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(api_server, '_AUTH_REQUIRED', True)

    response = asyncio.run(
        api_server.mammoth_chat(
            {
                'message': '/commit chore: unsafe',
                'agent_id': 'coding_agent',
                'mode': 'chat',
            }
        )
    )

    assert response['status'] == 'error'
    assert response['adapter'] == 'policy-guard'
    assert 'disabled in Mammoth Mind chat' in response['reply']


def test_mammoth_chat_gitops_is_disabled_in_optional_auth(monkeypatch):
    monkeypatch.setattr(api_server, '_AUTH_REQUIRED', False)

    response = asyncio.run(
        api_server.mammoth_chat(
            {
                'message': '/commit feat: ship it',
                'agent_id': 'coding_agent',
                'mode': 'chat',
            }
        )
    )

    assert response['status'] == 'error'
    assert response['adapter'] == 'policy-guard'
    assert 'disabled in Mammoth Mind chat' in response['reply']


def test_mammoth_repo_context_endpoint_returns_snapshot(monkeypatch):
    monkeypatch.setattr(api_server, '_AUTH_REQUIRED', False)
    monkeypatch.setattr(
        api_server,
        '_collect_repo_context_snapshot',
        lambda req: {'query': req.get('query'), 'snippets': [{'path': 'api_server.py'}]},
    )

    response = asyncio.run(
        api_server.mammoth_repo_context(
            {
                'repo_context': {
                    'query': 'atlas',
                    'files': ['api_server.py'],
                }
            }
        )
    )

    assert response['status'] == 'ok'
    assert response['repo_context']['query'] == 'atlas'
    assert response['repo_context']['snippets'][0]['path'] == 'api_server.py'


def test_normalize_repo_context_defaults_to_main_branch():
    normalized = api_server._normalize_repo_context_request({"query": "sdk"})
    assert normalized["branch"] == "main"


def test_normalize_repo_context_rejects_invalid_branch():
    normalized = api_server._normalize_repo_context_request({"query": "sdk", "branch": "main; rm -rf"})
    assert normalized["branch"] == "main"


def test_normalize_repo_context_owner_repo_reference_uses_default_root():
    normalized = api_server._normalize_repo_context_request({"query": "sdk", "root": "xxii-architect/mammoth_intro_ai"})
    assert normalized["requested_root"] == "xxii-architect/mammoth_intro_ai"
    assert normalized["root"] == str(api_server.ROOT)
    assert "GitHub owner/repo reference" in normalized["root_warning"]


def test_normalize_repo_context_missing_root_falls_back_to_default():
    normalized = api_server._normalize_repo_context_request({"query": "sdk", "root": "C:/missing/repo/path"})
    assert normalized["requested_root"] == "C:/missing/repo/path"
    assert normalized["root"] == str(api_server.ROOT)
    assert "not found on the backend host" in normalized["root_warning"]
