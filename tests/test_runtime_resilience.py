import asyncio

import api_server
import mammoth_os.llm_client as llm_client_mod


class BrokenClient:
    model = 'broken-model'

    async def generate(self, prompt: str, **kwargs):
        raise RuntimeError('insufficient_quota: billing blocked')


def test_runtime_status_snapshot_marks_local_fallback_as_degraded(monkeypatch):
    api_server._LATEST_RUNTIME_STATUS = {}
    monkeypatch.delenv("MAMMOTH_LLM_ADAPTER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setattr(api_server, '_read_env_vars', lambda: {})
    monkeypatch.setattr(api_server, '_ollama_running', lambda *_args, **_kwargs: False)

    snapshot = api_server._runtime_status_snapshot()

    assert snapshot['state'] == 'degraded'
    assert snapshot['active_adapter'] == 'local'
    assert snapshot['available_providers'] == ['local']
    assert 'issue' in snapshot
    assert 'next_action' in snapshot
    assert 'local-safe fallback mode' in snapshot['issue'].lower()
    assert 'DEEPSEEK_API_KEY' in snapshot['recommendation'] or 'OPENAI_API_KEY' in snapshot['recommendation']


def test_atlas_chat_replaces_raw_runtime_errors_with_safe_notice(monkeypatch):
    state = {}
    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(api_server, '_runtime_status_snapshot', lambda: {
        'state': 'degraded',
        'active_adapter': 'local',
        'active_model': 'local-adapter',
        'recommendation': 'Add OPENAI_API_KEY or start Ollama to restore a cloud-capable runtime.',
        'providers': [],
        'available_providers': ['local'],
        'fallback_chain': ['deepseek', 'openai', 'ollama', 'local'],
        'summary': {},
    })
    monkeypatch.setattr(llm_client_mod, 'get_llm_client', lambda config=None: BrokenClient())

    response = asyncio.run(
        api_server.atlas_chat(
            {
                'message': 'Help me with the next lesson step.',
                'mode': 'assistant',
                'page_context': {'current_page': 'atlas'},
            }
        )
    )

    assert response['status'] == 'ok'
    assert 'billing blocked' not in response['reply']
    assert 'safe fallback' in response['reply'].lower()
    assert response['runtime_status']['state'] == 'degraded'
    assert response['runtime_notice']['state'] == 'degraded'


def test_mammoth_chat_replaces_raw_runtime_errors_with_safe_notice(monkeypatch):
    state = {}
    monkeypatch.setattr(api_server, '_load_atlas_state', lambda: state)
    monkeypatch.setattr(api_server, '_save_atlas_state', lambda payload: None)
    monkeypatch.setattr(api_server, '_runtime_status_snapshot', lambda: {
        'state': 'degraded',
        'active_adapter': 'local',
        'active_model': 'local-adapter',
        'recommendation': 'Add OPENAI_API_KEY or start Ollama to restore a cloud-capable runtime.',
        'providers': [],
        'available_providers': ['local'],
        'fallback_chain': ['deepseek', 'openai', 'ollama', 'local'],
        'summary': {},
    })
    monkeypatch.setattr(llm_client_mod, 'get_llm_client', lambda config=None: BrokenClient())

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
    assert 'billing blocked' not in response['reply']
    assert 'safe fallback' in response['reply'].lower()
    assert response['runtime_status']['state'] == 'degraded'
    assert response['runtime_notice']['state'] == 'degraded'


def test_merge_latest_runtime_status_prefers_last_used_provider():
    api_server._LATEST_RUNTIME_STATUS = {}
    api_server._remember_runtime_status(
        {
            'state': 'degraded',
            'degraded_mode': True,
            'active_adapter': 'openai',
            'active_model': 'gpt-4o-mini',
            'effective_adapter': 'openai',
            'used_provider': 'local',
            'fallback_used': True,
            'fallback_reason': 'quota_or_billing',
        }
    )

    merged = api_server._merge_latest_runtime_status(
        {
            'state': 'ready',
            'degraded_mode': False,
            'active_adapter': 'openai',
            'active_model': 'gpt-4o-mini',
            'providers': [
                {'provider': 'openai', 'status': 'ready', 'available': True},
                {'provider': 'local', 'status': 'ready', 'available': True},
            ],
            'fallback_chain': ['deepseek', 'openai', 'ollama', 'local'],
        }
    )

    assert merged['active_provider'] == 'local'
    assert merged['fallback_used'] is True
    assert merged['providers'][0]['selected'] is True
    assert merged['providers'][0]['active'] is False
    assert merged['providers'][1]['active'] is True
    assert merged['providers'][1]['fallback_target'] is True
    assert merged['checked_at']
