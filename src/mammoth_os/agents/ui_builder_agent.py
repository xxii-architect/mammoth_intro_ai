import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from .base_agent import BaseAgent


class UIBuilderAgent(BaseAgent):
    """Scaffold a small Vite + React UI from a natural-language prompt.

    This is intentionally lightweight and deterministic so it works without any
    external tooling beyond Node/npm. The generated app is a good starter for
    demos, local previews, and future UI iteration.
    """

    name = "UIBuilderAgent"

    def __init__(self, router: Optional[Any] = None):
        super().__init__(router)

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    def _slugify(self, value: str) -> str:
        value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return value or "atlas-ui"

    def _title_case(self, value: str) -> str:
        return " ".join(part.capitalize() for part in value.split())

    def _to_component_name(self, value: str, suffix: str = "") -> str:
        parts = re.split(r"[^a-zA-Z0-9]+", value)
        name = "".join(part.capitalize() for part in parts if part)
        if not name:
            name = "Generated"
        if not name[0].isalpha():
            name = f"Atlas{name}"
        return f"{name}{suffix}"

    def _extract_filename(self, prompt_text: str) -> str:
        """
        Extract a clean filename from the prompt.
        If the prompt contains something like 'DashboardLayout.jsx',
        return exactly that. Otherwise, fall back to the first word + '.jsx'.
        """
        match = re.search(r"([A-Za-z0-9_/\\-]+\.jsx)", prompt_text)
        if match:
            return match.group(1)

        # fallback: first word + .jsx
        base = (prompt_text or "").split()[0] if (prompt_text or "").split() else "Component"
        # sanitize base
        base = re.sub(r"[^A-Za-z0-9_-]", "", base)
        return f"{base or 'Component'}.jsx"

    def _extract_css_filename(self, prompt_text: str) -> str:
        """Extract a clean CSS filename from the prompt, max 40 chars."""
        match = re.search(r"([A-Za-z0-9_-]+\.css)", prompt_text)
        if match:
            return match.group(1)
        base = (prompt_text or "").split()[0] if (prompt_text or "").split() else "style"
        base = re.sub(r"[^A-Za-z0-9_-]", "", base)
        return f"{(base or 'style')[:40]}.css"

    def _extract_hook_name(self, prompt_text: str) -> str:
        """Extract a clean JS hook filename stem from the prompt, max 40 chars."""
        match = re.search(r"use([A-Za-z0-9]+)", prompt_text)
        if match:
            return f"use{match.group(1)}"
        base = (prompt_text or "").split()[0] if (prompt_text or "").split() else "data"
        base = re.sub(r"[^A-Za-z0-9_]", "", base)
        return f"use{(base or 'data').capitalize()[:38]}"

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _ui_state_file(self) -> Path:
        return self._repo_root() / ".mammoth" / "atlas_ui_state.json"

    def _set_active_ui_dir(self, target_dir: Path) -> None:
        state_file = self._ui_state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps({"active_ui_project": str(target_dir.resolve())}, indent=2),
            encoding="utf-8",
        )

    def _resolve_active_ui_dir(self) -> Path:
        """
        Load the active UI project path from .mammoth/atlas_ui_state.json.
        Return a Path object. Raise a clear error if missing.
        """
        state_file = Path(".mammoth/atlas_ui_state.json")
        if not state_file.exists():
            raise RuntimeError("No active UI project. Run `atlas ui scaffold` first.")

        data = json.loads(state_file.read_text())
        raw_path = data.get("active_ui_project")
        if not raw_path:
            raise RuntimeError("Active UI project path missing in atlas_ui_state.json.")

        p = Path(raw_path)
        if not p.exists():
            raise RuntimeError(f"Active UI project path does not exist: {p}")

        return p

    def _resolve_target_ui_dir(self, target_dir: Optional[str] = None) -> Path:
        if target_dir:
            base_dir = Path(target_dir).expanduser()
            if not base_dir.is_absolute():
                base_dir = (Path.cwd() / base_dir).resolve()
            return base_dir
        return self._resolve_active_ui_dir()

    async def scaffold(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        """Generate a Vite React starter app for the given UI description."""
        prompt_text = (prompt or "ATLAS progress dashboard").strip()
        app_name = self._slugify(prompt_text)
        base_dir = Path(target_dir).expanduser() if target_dir else Path.cwd() / "ui" / app_name
        if not base_dir.is_absolute():
            base_dir = (Path.cwd() / base_dir).resolve()

        files: Dict[str, str] = {}
        title = self._title_case(prompt_text)
        if title.lower().startswith("atlas"):
            title = title.replace("Atlas", "ATLAS", 1)

        files["package.json"] = self._package_json(app_name)
        files["vite.config.js"] = self._vite_config()
        files["index.html"] = self._index_html(app_name)
        files["src/main.jsx"] = self._main_jsx()
        files["src/App.jsx"] = self._app_jsx(title, prompt_text)
        files["src/index.css"] = self._index_css()
        files["README.md"] = self._readme(app_name, title)

        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "src").mkdir(parents=True, exist_ok=True)

        for rel_path, content in files.items():
            target_path = base_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

        self._set_active_ui_dir(base_dir)

        return {
            "status": "ok",
            "app_name": app_name,
            "title": title,
            "target_dir": str(base_dir),
            "files": list(files.keys()),
            "next_steps": [
                "cd " + str(base_dir),
                "npm install",
                "npm run dev",
            ],
        }

    async def _write_stub_file(
        self,
        kind: str,
        prompt: str,
        relative_path: str,
        content: str,
        target_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        if not prompt_text:
            raise ValueError(f"{kind} prompt cannot be empty")

        self.log("INFO", f"{kind} prompt: {prompt_text}")
        base_dir = self._resolve_target_ui_dir(target_dir)
        target_path = (base_dir / relative_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        self._set_active_ui_dir(base_dir)
        return {
            "status": "ok",
            "kind": kind,
            "prompt": prompt_text,
            "target_dir": str(base_dir),
            "file": str(target_path),
            "relative_file": relative_path.replace("\\", "/"),
        }

    async def generate_component(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        filename = self._extract_filename(prompt_text)
        component_name = self._to_component_name(Path(filename).stem)
        rel_path = f"src/components/{filename}"
        active_dir = self._resolve_target_ui_dir(target_dir)
        target_path = active_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"""export default function {component_name}() {{
  // Placeholder generated by atlas ui component
  return <section className="glass-panel">{prompt_text}</section>
}}
"""
        return await self._write_stub_file("component", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_style(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        css_filename = self._extract_css_filename(prompt_text)
        rel_path = f"src/styles/{css_filename}"
        active_dir = self._resolve_target_ui_dir(target_dir)
        target_path = active_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = f""".glass-panel {{
  /* Placeholder generated by atlas ui style */
  background: rgba(10, 20, 40, 0.78);
  border: 1px solid rgba(102, 255, 255, 0.25);
  box-shadow: 0 0 24px rgba(130, 86, 255, 0.35);
}}

/* Prompt: {prompt_text} */
"""
        return await self._write_stub_file("style", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_backend(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        hook_name = self._extract_hook_name(prompt_text)
        rel_path = f"src/hooks/{hook_name}.js"
        active_dir = self._resolve_target_ui_dir(target_dir)
        target_path = active_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        export_fn = self._to_component_name(hook_name)
        content = f"""export function {export_fn}() {{
  // Placeholder generated by atlas ui backend
  return {{ status: 'todo', prompt: {prompt_text!r} }}
}}
"""
        return await self._write_stub_file("backend", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_graph(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        filename = self._extract_filename(prompt_text)
        stem = Path(filename).stem
        component_name = self._to_component_name(stem, suffix="Graph")
        rel_path = f"src/components/graphs/{stem}.jsx"
        active_dir = self._resolve_target_ui_dir(target_dir)
        target_path = active_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"""export default function {component_name}() {{
  // Placeholder generated by atlas ui graph
  return <div className="graph-shell">Graph placeholder: {prompt_text}</div>
}}
"""
        return await self._write_stub_file("graph", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_palette(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        filename = self._extract_filename(prompt_text)
        stem = Path(filename).stem
        component_name = self._to_component_name(stem, suffix="Palette")
        rel_path = f"src/components/palette/{stem}.jsx"
        active_dir = self._resolve_target_ui_dir(target_dir)
        target_path = active_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"""export default function {component_name}() {{
  // Placeholder generated by atlas ui palette
  return <div className="command-palette">Command palette placeholder: {prompt_text}</div>
}}
"""
        return await self._write_stub_file("palette", prompt_text, rel_path, content, target_dir=str(active_dir))

    def _package_json(self, app_name: str) -> str:
        return f'''{{
  "name": "{app_name}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.10"
  }}
}}
'''

    def _vite_config(self) -> str:
        return '''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
  },
})
'''

    def _index_html(self, app_name: str) -> str:
        return f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="Generated UI for {app_name}" />
    <title>{app_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
'''

    def _main_jsx(self) -> str:
        return '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
'''

    def _app_jsx(self, title: str, prompt_text: str) -> str:
        return f'''const stats = [
  {{ label: 'XP', value: '1,420', detail: '+120 this week' }},
  {{ label: 'Lessons', value: '18', detail: '3 in progress' }},
  {{ label: 'Streak', value: '7 days', detail: 'Keep the momentum' }},
]

const activity = [
  {{ title: 'ATLAS lesson passed', subtitle: 'Python functions', time: '12m ago' }},
  {{ title: 'New prompt logged', subtitle: 'UI scaffold requested', time: '27m ago' }},
  {{ title: 'Sandbox run succeeded', subtitle: 'Generated code validated', time: '1h ago' }},
]

const lessons = [
  {{ title: 'Adaptive quiz', status: 'Ready' }},
  {{ title: 'Code review loop', status: 'In progress' }},
  {{ title: 'Progress dashboard', status: 'Next' }},
]

export default function App() {{
  return (
    <div className="app-shell">
      <header className="hero-card">
        <div>
          <p className="eyebrow">MammothOS / ATLAS</p>
          <h1>{title}</h1>
          <p className="hero-copy">
            Generated from the prompt: <strong>{prompt_text}</strong>
          </p>
        </div>
        <button className="primary-btn">Run a new lesson</button>
      </header>

      <section className="stats-grid">
        {{stats.map((item) => (
          <article className="stat-card" key={{item.label}}>
            <p className="stat-label">{{item.label}}</p>
            <h2>{{item.value}}</h2>
            <p className="stat-detail">{{item.detail}}</p>
          </article>
        ))}}
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-header">
            <h3>Recent activity</h3>
            <span>Live</span>
          </div>
          <ul className="stack-list">
            {{activity.map((item) => (
              <li key={{item.title}}>
                <div>
                  <strong>{{item.title}}</strong>
                  <p>{{item.subtitle}}</p>
                </div>
                <span>{{item.time}}</span>
              </li>
            ))}}
          </ul>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h3>Next lessons</h3>
            <span>Suggested</span>
          </div>
          <ul className="stack-list">
            {{lessons.map((item) => (
              <li key={{item.title}}>
                <div>
                  <strong>{{item.title}}</strong>
                </div>
                <span>{{item.status}}</span>
              </li>
            ))}}
          </ul>
        </article>
      </section>
    </div>
  )
}}
'''

    def _index_css(self) -> str:
        return '''body {
  margin: 0;
  background: linear-gradient(135deg, #07111f, #112642);
  color: #f5f9ff;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

* { box-sizing: border-box; }

#root { min-height: 100vh; }

.app-shell {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px;
}

.hero-card, .stat-card, .panel {
  background: rgba(8, 20, 36, 0.86);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 20px;
  box-shadow: 0 18px 45px rgba(0,0,0,0.25);
}

.hero-card {
  padding: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.28em;
  color: #78c1ff;
  font-size: 0.78rem;
  margin-bottom: 8px;
}

.hero-copy { color: #9fb7cf; max-width: 640px; }

.primary-btn {
  padding: 10px 16px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(90deg, #4f8cff, #70d3ff);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.stat-card { padding: 18px; }
.stat-label { color: #7fb8e6; text-transform: uppercase; letter-spacing: 0.16em; font-size: 0.75rem; }
.stat-card h2 { font-size: 1.8rem; margin: 8px 0; }
.stat-detail { color: #9fb7cf; margin: 0; }

.content-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.panel { padding: 18px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.panel-header span { color: #78c1ff; font-size: 0.9rem; }
.stack-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.stack-list li { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.08); }
.stack-list li:first-child { border-top: 0; }
.stack-list p { margin: 4px 0 0; color: #9fb7cf; }
.stack-list span { color: #78c1ff; font-size: 0.9rem; }
'''

    def _readme(self, app_name: str, title: str) -> str:
        return f'''# {title}

Generated by UIBuilderAgent for the prompt: `{app_name}`.

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:3000 to preview the app.
'''


async def build_ui(prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
    agent = UIBuilderAgent(router=None)
    return await agent.scaffold(prompt, target_dir=target_dir)
