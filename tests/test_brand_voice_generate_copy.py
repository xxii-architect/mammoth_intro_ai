# tests/test_brand_voice_generate_copy.py

from pathlib import Path
from mammoth_os.agents.brand_voice_agent import BrandVoiceAgent

def test_generate_copy_writes_file(tmp_path):
    agent = BrandVoiceAgent(router=None)
    target = tmp_path / "out.txt"
    res = agent._generate_copy(str(target), {"theme": "TestTheme"})
    assert isinstance(res, dict)
    assert res.get("status") == "ok"
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "TestTheme" in content
