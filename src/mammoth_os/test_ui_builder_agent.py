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


def test_ui_builder_agent_scaffold_includes_shared_tokens_and_components(tmp_path):
    target_dir = tmp_path / "atlas-dashboard"
    agent = UIBuilderAgent(router=None)

    result = asyncio.run(agent.scaffold("ATLAS progress dashboard", target_dir=str(target_dir)))

    assert result["status"] == "ok"
    assert (target_dir / "src" / "styles" / "tokens.css").exists()
    assert (target_dir / "src" / "components" / "ui" / "MetricCard.jsx").exists()
    assert (target_dir / "src" / "components" / "ui" / "SectionPanel.jsx").exists()
    assert (target_dir / "src" / "components" / "ui" / "StatusPill.jsx").exists()
    assert "shared_components" in result

    app_source = (target_dir / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "MetricCard" in app_source
    assert "SectionPanel" in app_source
    assert "StatusPill" in app_source

    css_source = (target_dir / "src" / "index.css").read_text(encoding="utf-8")
    assert "@import './styles/tokens.css';" in css_source


def test_ui_builder_agent_generators_emit_reusable_scaffolds(tmp_path):
    target_dir = tmp_path / "atlas-dashboard"
    agent = UIBuilderAgent(router=None)
    asyncio.run(agent.scaffold("ATLAS progress dashboard", target_dir=str(target_dir)))

    component_result = asyncio.run(
        agent.generate_component(
            "Create DashboardLayout with reusable header and footer",
            target_dir=str(target_dir),
        )
    )
    component_source = Path(component_result["file"]).read_text(encoding="utf-8")
    assert "children" in component_source
    assert "footer" in component_source
    assert "atlas-card" in component_source

    style_result = asyncio.run(agent.generate_style("Add command center tokens", target_dir=str(target_dir)))
    style_source = Path(style_result["file"]).read_text(encoding="utf-8")
    assert ":root" in style_source
    assert ".atlas-status" in style_source

    backend_result = asyncio.run(agent.generate_backend("Create ui state hook", target_dir=str(target_dir)))
    backend_source = Path(backend_result["file"]).read_text(encoding="utf-8")
    assert "useCallback" in backend_source
    assert "reset" in backend_source

    graph_result = asyncio.run(agent.generate_graph("Build activity trend graph", target_dir=str(target_dir)))
    graph_source = Path(graph_result["file"]).read_text(encoding="utf-8")
    assert "sampleSeries" in graph_source
    assert "polyline" in graph_source
