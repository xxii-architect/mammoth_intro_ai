import asyncio
from pathlib import Path

from mammoth_os.agents.ui_builder_agent import UIBuilderAgent


def test_ui_builder_agent_scaffolds_vite_app(tmp_path):
    target_dir = tmp_path / "atlas-dashboard"
    agent = UIBuilderAgent(router=None)

    result = asyncio.run(agent.scaffold("ATLAS progress dashboard", target_dir=str(target_dir)))

    assert result["status"] == "ok"
    assert (target_dir / "package.json").exists()
    assert (target_dir / "vite.config.js").exists()
    assert (target_dir / "src" / "App.jsx").exists()
    assert (target_dir / "src" / "index.css").exists()
    assert "package.json" in result["files"]
    assert result["target_dir"] == str(target_dir.resolve())


def test_ui_builder_agent_component_uses_extracted_filename(tmp_path):
    target_dir = tmp_path / "atlas-dashboard"
    agent = UIBuilderAgent(router=None)
    asyncio.run(agent.scaffold("ATLAS progress dashboard", target_dir=str(target_dir)))

    result = asyncio.run(
        agent.generate_component(
            "Create DashboardLayout.jsx with neon command center shell and module slots",
            target_dir=str(target_dir),
        )
    )

    assert result["status"] == "ok"
    assert result["relative_file"] == "src/components/DashboardLayout.jsx"
    assert (target_dir / "src" / "components" / "DashboardLayout.jsx").exists()


def test_ui_builder_agent_component_falls_back_to_first_word_filename(tmp_path):
    target_dir = tmp_path / "atlas-dashboard"
    agent = UIBuilderAgent(router=None)
    asyncio.run(agent.scaffold("ATLAS progress dashboard", target_dir=str(target_dir)))

    result = asyncio.run(
        agent.generate_component(
            "Dashboard glass panel with widget zones and animated metric strips",
            target_dir=str(target_dir),
        )
    )

    assert result["status"] == "ok"
    assert result["relative_file"] == "src/components/Dashboard.jsx"
    assert (target_dir / "src" / "components" / "Dashboard.jsx").exists()
