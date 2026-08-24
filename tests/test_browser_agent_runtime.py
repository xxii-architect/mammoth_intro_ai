import requests

from mammoth_os.agent_registry import load_agent
from mammoth_os.agents.browser_agent import BrowserAgent


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200, content_type: str = "text/html", url: str = "https://example.com/page"):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": content_type}


def test_browser_agent_snaps_html_pages(monkeypatch):
    html = """
    <html>
      <head>
        <title>Example Page</title>
        <meta name="description" content="A simple browser snapshot." />
      </head>
      <body>
        <h1>Welcome</h1>
        <h2>Details</h2>
        <p>One two three four.</p>
        <a href="/docs">Docs</a>
      </body>
    </html>
    """

    def fake_request(self, method, url, headers=None, data=None, json=None, timeout=0, allow_redirects=True):
        return _FakeResponse(html, url=url)

    monkeypatch.setattr(requests.Session, "request", fake_request)
    agent = BrowserAgent(router=None)
    result = agent.run({"url": "https://example.com", "max_links": 3})

    assert result["status"] == "ok"
    assert result["mode"] == "browser_automation_v2"
    assert result["title"] == "Example Page"
    assert result["description"] == "A simple browser snapshot."
    assert result["headings"] == ["Welcome", "Details"]
    assert result["links"][0]["href"] == "https://example.com/docs"
    assert result["summary"].startswith("Example Page")
    assert result["word_count"] > 0
    assert result["execution"]["passed"] is True


def test_browser_agent_requires_a_url_when_prompt_is_ambiguous():
    agent = BrowserAgent(router=None)
    result = agent.run("summarize the homepage")

    assert result["status"] == "needs_context"
    assert "Provide a URL" in result["message"]


def test_browser_agent_supports_stateful_actions_and_replay(monkeypatch, tmp_path):
    pages = {
        "https://example.com/start": "<html><head><title>Start</title></head><body><a href=\"/next\">Next</a></body></html>",
        "https://example.com/next": "<html><head><title>Next</title></head><body><h1>Done</h1></body></html>",
    }

    def fake_request(self, method, url, headers=None, data=None, json=None, timeout=0, allow_redirects=True):
        return _FakeResponse(pages[url], url=url)

    monkeypatch.setattr(requests.Session, "request", fake_request)
    agent = BrowserAgent(router=None, storage_root=str(tmp_path))
    flow = agent.run(
        {
            "session_id": "session-a",
            "actions": [
                {"action": "navigate", "url": "https://example.com/start"},
                {"action": "click", "href": "/next"},
            ],
        }
    )

    assert flow["status"] == "ok"
    assert flow["action_count"] == 2
    assert flow["title"] == "Next"

    replay = agent.run({"action": "replay", "replay_id": flow["replay_id"]})
    assert replay["status"] == "ok"
    assert replay["replay"]["replay_id"] == flow["replay_id"]


def test_browser_agent_is_loadable_from_registry():
    agent = load_agent("browser", None)
    assert isinstance(agent, BrowserAgent)
