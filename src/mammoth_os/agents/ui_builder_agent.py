import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


from .base_agent import BaseAgent
from mammoth_os.llm_client import get_llm_client, extract_code_from_text


class UIBuilderAgent(BaseAgent):
    """Scaffold a small Vite + React UI from a natural-language prompt.

    This is intentionally lightweight and deterministic so it works without any
    external tooling beyond Node/npm. The generated app is a good starter for
    demos, local previews, and future UI iteration.
    """

    name = "UIBuilderAgent"

    def __init__(self, router: Optional[Any] = None):
        super().__init__(router)

    def _resolve_preview_dir(self, target_dir: Optional[str], prompt_text: str) -> Path:
        if target_dir:
            base_dir = Path(target_dir).expanduser()
            if not base_dir.is_absolute():
                base_dir = (Path.cwd() / base_dir).resolve()
            return base_dir
        try:
            return self._resolve_target_ui_dir(None)
        except Exception:
            return (Path.cwd() / "ui" / self._slugify(prompt_text or "atlas-ui")).resolve()

    def _normalized_action(self, request: Dict[str, Any], prompt_text: str) -> str:
        action = str(request.get("action") or request.get("operation") or request.get("kind") or "").strip().lower()
        if action in {"generate_component", "component"}:
            return "component"
        if action in {"generate_style", "style"}:
            return "style"
        if action in {"generate_backend", "backend", "hook"}:
            return "backend"
        if action in {"generate_graph", "graph"}:
            return "graph"
        if action in {"generate_palette", "palette"}:
            return "palette"
        if action == "scaffold":
            return "scaffold"
        lowered = prompt_text.lower()
        if any(token in lowered for token in ["scaffold", "starter app", "new app", "new ui"]):
            return "scaffold"
        if "palette" in lowered:
            return "palette"
        if "graph" in lowered:
            return "graph"
        if "hook" in lowered or "state" in lowered:
            return "backend"
        if "style" in lowered or "token" in lowered:
            return "style"
        return "component"

    async def run(self, payload: Any) -> Dict[str, Any]:
        request = payload if isinstance(payload, dict) else {"prompt": str(payload or "")}
        prompt_text = str(request.get("prompt") or request.get("task") or request.get("description") or request.get("content") or "").strip()
        approval_mode = bool(request.get("approval_mode") or request.get("preview_only"))
        target_dir = request.get("target_dir") if isinstance(request.get("target_dir"), str) else None
        action = self._normalized_action(request, prompt_text)
        preview_dir = self._resolve_preview_dir(target_dir, prompt_text)
        approval_contract = {
            "operation": f"ui_{action}",
            "target": str(preview_dir),
            "requires_write": True,
        }
        task_card = {
            "title": f"UIBuilder {action}",
            "action": action,
            "prompt": prompt_text,
            "target_dir": str(preview_dir),
            "approval_mode": approval_mode,
        }
        observability = {
            "structured_output_version": "v2",
            "action": action,
            "approval_mode": approval_mode,
            "target_dir": str(preview_dir),
            "prompt_length": len(prompt_text),
        }
        if approval_mode:
            files = []
            if action == "scaffold":
                scaffold_app = self._slugify(prompt_text or "atlas-ui")
                title = self._title_case(prompt_text or "ATLAS UI")
                if title.lower().startswith("atlas"):
                    title = title.replace("Atlas", "ATLAS", 1)
                scaffold_files = self._scaffold_files(scaffold_app, title, prompt_text)
                files = [{"path": rel_path, "size": len(content)} for rel_path, content in scaffold_files.items()]
            else:
                filename = self._extract_filename(prompt_text)
                if action == "style":
                    files = [{"path": f"src/styles/{self._extract_css_filename(prompt_text)}", "size": 0}]
                elif action == "backend":
                    files = [{"path": f"src/hooks/{self._extract_hook_name(prompt_text)}.js", "size": 0}]
                elif action == "graph":
                    stem = Path(filename).stem
                    files = [{"path": f"src/components/graphs/{stem}.jsx", "size": 0}]
                elif action == "palette":
                    files = [{"path": f"src/components/palette/{filename}.tsx", "size": 0}]
                else:
                    files = [{"path": f"src/components/{filename}", "size": 0}]
            return {
                "status": "pending_approval",
                "agent": "ui_builder",
                "structured_output_version": "v2",
                "approval_safe": True,
                "action": action,
                "prompt": prompt_text,
                "target_dir": str(preview_dir),
                "approval_contract": approval_contract,
                "preview": {
                    "summary": f"Preview {action} changes for {prompt_text or 'UI builder task'}",
                    "files": files,
                    "task_card": task_card,
                },
                "task_card": task_card,
                "observability": observability,
            }

        if action == "scaffold":
            result = await self.scaffold(prompt_text, target_dir=str(preview_dir))
        elif action == "style":
            result = await self.generate_style(prompt_text, target_dir=str(preview_dir))
        elif action == "backend":
            result = await self.generate_backend(prompt_text, target_dir=str(preview_dir))
        elif action == "graph":
            result = await self.generate_graph(prompt_text, target_dir=str(preview_dir))
        elif action == "palette":
            result = await self.generate_palette(prompt_text, target_dir=str(preview_dir))
        else:
            result = await self.generate_component(prompt_text, target_dir=str(preview_dir))

        result.update({
            "agent": "ui_builder",
            "action": action,
            "approval_safe": True,
            "approval_contract": approval_contract,
            "task_card": task_card,
            "observability": observability,
            "structured_output_version": "v2",
        })
        return result

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

    def _extract_filename(self, prompt: str) -> str:
        """Derive a PascalCase component filename from the key nouns in the prompt."""
        import re
        explicit = re.search(r"([A-Za-z0-9_-]+\.(?:jsx|tsx|js|ts|css))", prompt)
        if explicit:
            return explicit.group(1)

        _SKIP = {
            "add", "create", "build", "make", "promote", "update", "fix", "write",
            "generate", "implement", "a", "an", "the", "for", "into", "with",
            "and", "or", "of", "to", "in", "on", "at", "responsive", "real",
            "new", "full", "complete", "simple", "support",
        }
        words = re.findall(r"[A-Za-z]+", prompt)
        meaningful = [w for w in words if w.lower() not in _SKIP]
        name = "".join(w.capitalize() for w in meaningful[:1]) or "Component"
        return f"{name}.jsx"

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

        title = self._title_case(prompt_text)
        if title.lower().startswith("atlas"):
            title = title.replace("Atlas", "ATLAS", 1)
        files = self._scaffold_files(app_name=app_name, title=title, prompt_text=prompt_text)

        base_dir.mkdir(parents=True, exist_ok=True)
        (base_dir / "src").mkdir(parents=True, exist_ok=True)

        for rel_path, content in files.items():
            target_path = base_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

        self._set_active_ui_dir(base_dir)

        return {
            "status": "ok",
            "agent": "ui_builder",
            "structured_output_version": "v2",
            "approval_safe": True,
            "app_name": app_name,
            "title": title,
            "target_dir": str(base_dir),
            "files": list(files.keys()),
            "shared_components": [
                "src/components/ui/MetricCard.jsx",
                "src/components/ui/SectionPanel.jsx",
                "src/components/ui/StatusPill.jsx",
                "src/components/ui/index.js",
                "src/styles/tokens.css",
            ],
            "next_steps": [
                "cd " + str(base_dir),
                "npm install",
                "npm run dev",
            ],
            "task_card": {
                "title": f"Scaffold {app_name}",
                "summary": f"Generate a starter UI for {title}.",
                "target_dir": str(base_dir),
                "file_count": len(files),
            },
            "observability": {
                "structured_output_version": "v2",
                "kind": "scaffold",
                "file_count": len(files),
                "target_dir": str(base_dir),
            },
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
            "agent": "ui_builder",
            "structured_output_version": "v2",
            "approval_safe": True,
            "kind": kind,
            "prompt": prompt_text,
            "target_dir": str(base_dir),
            "file": str(target_path),
            "relative_file": relative_path.replace("\\", "/"),
            "task_card": {
                "title": f"{kind.title()} {target_path.name}",
                "summary": prompt_text,
                "target_dir": str(base_dir),
                "file": str(target_path),
            },
            "observability": {
                "structured_output_version": "v2",
                "kind": kind,
                "prompt_length": len(prompt_text),
                "target_dir": str(base_dir),
                "file": str(target_path),
            },
        }

    def _scaffold_files(self, app_name: str, title: str, prompt_text: str) -> Dict[str, str]:
        return {
            "package.json": self._package_json(app_name),
            "vite.config.js": self._vite_config(),
            "index.html": self._index_html(app_name),
            "src/main.jsx": self._main_jsx(),
            "src/App.jsx": self._app_jsx(title, prompt_text),
            "src/index.css": self._index_css(),
            "src/styles/tokens.css": self._tokens_css(),
            "src/components/ui/MetricCard.jsx": self._metric_card_component(),
            "src/components/ui/SectionPanel.jsx": self._section_panel_component(),
            "src/components/ui/StatusPill.jsx": self._status_pill_component(),
            "src/components/ui/index.js": self._ui_index(),
            "README.md": self._readme(app_name, title),
        }

    async def generate_component(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        filename = self._extract_filename(prompt_text)
        component_name = self._to_component_name(Path(filename).stem)
        rel_path = f"src/components/{filename}"
        active_dir = self._resolve_target_ui_dir(target_dir)
        title_literal = json.dumps(prompt_text or "Generated component")
        content = (
            "export default function __NAME__({\n"
            "  title = __TITLE__,\n"
            '  eyebrow = "Atlas UI",\n'
            "  children,\n"
            '  tone = "cyan",\n'
            '  className = "",\n'
            "  footer,\n"
            "}) {\n"
            '  const classes = ["atlas-card", `tone-${tone}`, className].filter(Boolean).join(" ")\n\n'
            "  return (\n"
            '    <article className={classes} data-tone={tone}>\n'
            '      <header className="atlas-card__header">\n'
            '        <p className="atlas-card__eyebrow">{eyebrow}</p>\n'
            '        <h3 className="atlas-card__title">{title}</h3>\n'
            "      </header>\n"
            '      <div className="atlas-card__body">\n'
            "        {children ?? <p className=\"atlas-card__copy\">__PROMPT__</p>}\n"
            "      </div>\n"
            '      {footer ? <footer className="atlas-card__footer">{footer}</footer> : null}\n'
            "    </article>\n"
            "  )\n"
            "}\n"
        ).replace("__NAME__", component_name).replace("__TITLE__", title_literal).replace("__PROMPT__", prompt_text or "Generated component")
        return await self._write_stub_file("component", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_style(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        css_filename = self._extract_css_filename(prompt_text)
        rel_path = f"src/styles/{css_filename}"
        active_dir = self._resolve_target_ui_dir(target_dir)
        content = f""":root {{
  color-scheme: dark;
  --atlas-bg: #07111f;
  --atlas-bg-elevated: #0c1729;
  --atlas-surface: rgba(8, 20, 36, 0.88);
  --atlas-border: rgba(124, 192, 255, 0.18);
  --atlas-text: #f5f9ff;
  --atlas-text-muted: #9fb7cf;
  --atlas-accent: #70d3ff;
  --atlas-accent-strong: #4f8cff;
  --atlas-accent-soft: rgba(112, 211, 255, 0.18);
  --atlas-radius-lg: 20px;
  --atlas-radius-md: 14px;
  --atlas-radius-sm: 10px;
  --atlas-shadow: 0 18px 45px rgba(0, 0, 0, 0.25);
  --atlas-gap: 16px;
}}

.atlas-card {{
  background: var(--atlas-surface);
  border: 1px solid var(--atlas-border);
  border-radius: var(--atlas-radius-lg);
  box-shadow: var(--atlas-shadow);
  padding: 18px;
}}

.atlas-card__header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}}

.atlas-card__eyebrow {{
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.72rem;
  color: var(--atlas-accent);
}}

.atlas-card__title {{
  margin: 0;
  color: var(--atlas-text);
}}

.atlas-card__copy {{
  margin: 0;
  color: var(--atlas-text-muted);
}}

.atlas-card__footer {{
  margin-top: 14px;
  color: var(--atlas-text-muted);
}}

.tone-cyan {{
  border-color: rgba(112, 211, 255, 0.28);
}}

.tone-violet {{
  border-color: rgba(130, 86, 255, 0.28);
}}

.tone-emerald {{
  border-color: rgba(66, 225, 171, 0.28);
}}

.atlas-status {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--atlas-border);
  color: var(--atlas-text);
  background: var(--atlas-accent-soft);
  font-size: 0.82rem;
  letter-spacing: 0.04em;
}}

/* Prompt: {prompt_text} */
"""
        return await self._write_stub_file("style", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_backend(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        hook_name = self._extract_hook_name(prompt_text)
        rel_path = f"src/hooks/{hook_name}.js"
        active_dir = self._resolve_target_ui_dir(target_dir)
        export_fn = self._to_component_name(hook_name)
        content = (
            "import { useCallback, useState } from 'react'\n\n"
            f"export function {export_fn}(initialValue = null) {{\n"
            "  const [value, setValue] = useState(initialValue)\n"
            "  const [loading, setLoading] = useState(false)\n"
            "  const [error, setError] = useState(null)\n\n"
            "  const run = useCallback(async (nextValue) => {\n"
            "    setLoading(true)\n"
            "    setError(null)\n"
            "    try {\n"
            "      const resolved = typeof nextValue === 'function' ? await nextValue() : nextValue\n"
            "      setValue(resolved)\n"
            "      return resolved\n"
            "    } catch (err) {\n"
            "      const message = err instanceof Error ? err.message : 'Unknown error'\n"
            "      setError(message)\n"
            "      throw err\n"
            "    } finally {\n"
            "      setLoading(false)\n"
            "    }\n"
            "  }, [])\n\n"
            "  const reset = useCallback(() => {\n"
            "    setValue(initialValue)\n"
            "    setError(null)\n"
            "    setLoading(false)\n"
            "  }, [initialValue])\n\n"
            "  return { value, loading, error, run, reset }\n"
            "}\n"
        )
        return await self._write_stub_file("backend", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_graph(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        filename = self._extract_filename(prompt_text)
        stem = Path(filename).stem
        component_name = self._to_component_name(stem, suffix="Graph")
        rel_path = f"src/components/graphs/{stem}.jsx"
        active_dir = self._resolve_target_ui_dir(target_dir)
        title_literal = json.dumps(prompt_text or "Generated graph")
        content = (
            "const sampleSeries = [18, 24, 22, 31, 28, 37, 42, 39, 46, 52]\n\n"
            f"export default function {component_name}({{\n"
            "  title = __TITLE__,\n"
            '  subtitle = "Generated graph shell",\n'
            "  points = sampleSeries,\n"
            "}) {\n"
            "  const width = 320\n"
            "  const height = 140\n"
            "  const max = Math.max(...points, 1)\n"
            "  const step = points.length > 1 ? width / (points.length - 1) : width\n"
            "  const scaled = points.map((value, index) => {\n"
            "    const x = index * step\n"
            "    const y = height - (value / max) * height\n"
            "    return `${x},${y}`\n"
            "  })\n"
            "  const path = scaled.join(' ')\n\n"
            "  return (\n"
            '    <section className="atlas-graph">\n'
            '      <header className="atlas-graph__header">\n'
            "        <h3>{title}</h3>\n"
            "        <p>{subtitle}</p>\n"
            "      </header>\n"
            "      <svg viewBox={`0 0 ${width} ${height}`} className=\"atlas-graph__svg\" role=\"img\" aria-label={title}>\n"
            '        <polyline fill="none" stroke="currentColor" strokeWidth="4" points={path} />\n'
            "      </svg>\n"
            "    </section>\n"
            "  )\n"
            "}\n"
        ).replace("__TITLE__", title_literal)
        return await self._write_stub_file("graph", prompt_text, rel_path, content, target_dir=str(active_dir))

    async def generate_palette(self, prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
        prompt_text = (prompt or "").strip()
        filename = self._extract_filename(prompt_text)
        component_name = self._to_component_name(Path(filename).stem)
        rel_path = f"src/components/palette/{filename}.tsx"
        active_dir = self._resolve_target_ui_dir(target_dir)

        llm_prompt = (
            f"You are an expert React + TypeScript developer.\n"
            f"Generate a single, complete, production-quality React functional component.\n"
            f"Task: {prompt_text}\n\n"
            f"Component name: `{component_name}`\n"
            f"Use TypeScript interfaces, token-aware styling, and reusable props.\n"
            f"No placeholder comments — write real logic.\n\n"
            f"Return ONLY the code inside a ```tsx code block."
        )

        try:
            client = get_llm_client()
            raw = await client.generate(llm_prompt, max_tokens=8192, temperature=0.3)
            content = extract_code_from_text(raw) or raw
        except Exception as exc:
            self.log("ERROR", f"generate_palette LLM call failed: {exc}")
            content = (
                f"export default function {component_name}({{\n"
                f"  title = {json.dumps(prompt_text or 'Palette component')},\n"
                "  children,\n"
                '  className = "",\n'
                "}) {\n"
                '  const classes = ["atlas-card", className].filter(Boolean).join(" ")\n\n'
                "  return (\n"
                "    <article className={classes}>\n"
                '      <header className="atlas-card__header">\n'
                '        <p className="atlas-card__eyebrow">Palette</p>\n'
                '        <h3 className="atlas-card__title">{title}</h3>\n'
                "      </header>\n"
                '      <div className="atlas-card__body">\n'
                f"        {{children ?? <p className=\"atlas-card__copy\">LLM generation failed: {exc}</p>}}\n"
                "      </div>\n"
                "    </article>\n"
                "  )\n"
                "}\n"
            )

        return await self._write_stub_file("palette", prompt_text, rel_path, content, target_dir=str(active_dir))

    def _ui_index(self) -> str:
        return """export { MetricCard } from './MetricCard'
export { SectionPanel } from './SectionPanel'
export { StatusPill } from './StatusPill'
"""

    def _metric_card_component(self) -> str:
        return """export function MetricCard({
  label,
  value,
  detail,
  tone = 'cyan',
  className = '',
}) {
  const classes = ['atlas-card', `tone-${tone}`, className].filter(Boolean).join(' ')

  return (
    <article className={classes}>
      <p className="atlas-card__eyebrow">{label}</p>
      <h3 className="atlas-card__title">{value}</h3>
      {detail ? <p className="atlas-card__copy">{detail}</p> : null}
    </article>
  )
}
"""

    def _section_panel_component(self) -> str:
        return """export function SectionPanel({
  title,
  badge,
  children,
  className = '',
}) {
  const classes = ['atlas-card', 'atlas-panel', className].filter(Boolean).join(' ')

  return (
    <section className={classes}>
      <header className="atlas-panel__header">
        <div>
          <p className="atlas-card__eyebrow">{badge}</p>
          <h3 className="atlas-card__title">{title}</h3>
        </div>
      </header>
      <div className="atlas-panel__body">{children}</div>
    </section>
  )
}
"""

    def _status_pill_component(self) -> str:
        return """export function StatusPill({
  tone = 'cyan',
  children,
}) {
  const classes = ['atlas-status', `tone-${tone}`].join(' ')
  return <span className={classes}>{children}</span>
}
"""

    def _tokens_css(self) -> str:
        return """:root {
  color-scheme: dark;
  --atlas-bg: #07111f;
  --atlas-bg-elevated: #0c1729;
  --atlas-surface: rgba(8, 20, 36, 0.88);
  --atlas-border: rgba(124, 192, 255, 0.18);
  --atlas-text: #f5f9ff;
  --atlas-text-muted: #9fb7cf;
  --atlas-accent: #70d3ff;
  --atlas-accent-strong: #4f8cff;
  --atlas-accent-soft: rgba(112, 211, 255, 0.18);
  --atlas-radius-lg: 20px;
  --atlas-radius-md: 14px;
  --atlas-radius-sm: 10px;
  --atlas-shadow: 0 18px 45px rgba(0, 0, 0, 0.25);
  --atlas-gap: 16px;
}

.atlas-card {
  background: var(--atlas-surface);
  border: 1px solid var(--atlas-border);
  border-radius: var(--atlas-radius-lg);
  box-shadow: var(--atlas-shadow);
  padding: 18px;
}

.atlas-card__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.atlas-card__eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.72rem;
  color: var(--atlas-accent);
}

.atlas-card__title {
  margin: 0;
  color: var(--atlas-text);
}

.atlas-card__copy {
  margin: 0;
  color: var(--atlas-text-muted);
}

.atlas-card__footer {
  margin-top: 14px;
  color: var(--atlas-text-muted);
}

.atlas-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--atlas-border);
  color: var(--atlas-text);
  background: var(--atlas-accent-soft);
  font-size: 0.82rem;
  letter-spacing: 0.04em;
}

.atlas-graph {
  padding: 18px;
  border-radius: var(--atlas-radius-lg);
  background: var(--atlas-surface);
  border: 1px solid var(--atlas-border);
}

.atlas-graph__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.atlas-graph__header h3,
.atlas-graph__header p {
  margin: 0;
}

.tone-cyan { border-color: rgba(112, 211, 255, 0.28); }
.tone-violet { border-color: rgba(130, 86, 255, 0.28); }
.tone-emerald { border-color: rgba(66, 225, 171, 0.28); }

.atlas-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--atlas-border);
  color: var(--atlas-text);
  background: var(--atlas-accent-soft);
  font-size: 0.82rem;
  letter-spacing: 0.04em;
}
"""

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
        return """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""

    def _app_jsx(self, title: str, prompt_text: str) -> str:
        return f"""import {{ MetricCard, SectionPanel, StatusPill }} from './components/ui'

const stats = [
  {{ label: 'XP', value: '1,420', detail: '+120 this week', tone: 'cyan' }},
  {{ label: 'Lessons', value: '18', detail: '3 in progress', tone: 'violet' }},
  {{ label: 'Streak', value: '7 days', detail: 'Keep the momentum', tone: 'emerald' }},
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
    <main className="app-shell">
      <header className="hero-card">
        <div>
          <p className="eyebrow">MammothOS / ATLAS</p>
          <h1>{title}</h1>
          <p className="hero-copy">
            Generated from the prompt: <strong>{prompt_text}</strong>
          </p>
        </div>
        <StatusPill tone="cyan">Live scaffold</StatusPill>
      </header>

      <section className="stats-grid">
        {{stats.map((item) => (
          <MetricCard
            key={{item.label}}
            label={{item.label}}
            value={{item.value}}
            detail={{item.detail}}
            tone={{item.tone}}
          />
        ))}}
      </section>

      <section className="content-grid">
        <SectionPanel title="Recent activity" badge="Live">
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
        </SectionPanel>

        <SectionPanel title="Next lessons" badge="Suggested">
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
        </SectionPanel>
      </section>
    </main>
  )
}}
"""

    def _index_css(self) -> str:
        return """@import './styles/tokens.css';

body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at top, rgba(112, 211, 255, 0.12), transparent 30%),
    linear-gradient(135deg, var(--atlas-bg), var(--atlas-bg-elevated));
  color: var(--atlas-text);
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

* {
  box-sizing: border-box;
}

#root {
  min-height: 100vh;
}

.app-shell {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px;
  display: grid;
  gap: var(--atlas-gap);
}

.hero-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 24px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.28em;
  color: var(--atlas-accent);
  font-size: 0.78rem;
  margin: 0 0 8px;
}

.hero-copy {
  color: var(--atlas-text-muted);
  max-width: 640px;
  margin: 10px 0 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.atlas-panel {
  display: grid;
  gap: 12px;
}

.atlas-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.atlas-panel__body {
  min-height: 100%;
}

.stack-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
}

.stack-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.stack-list li:first-child {
  border-top: 0;
}

.stack-list p {
  margin: 4px 0 0;
  color: var(--atlas-text-muted);
}

.stack-list span {
  color: var(--atlas-accent);
  font-size: 0.9rem;
}
"""

    def _readme(self, app_name: str, title: str) -> str:
        return f"""# {title}

Generated by UIBuilderAgent for the prompt: `{app_name}`.

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:3000 to preview the app.
"""


async def build_ui(prompt: str, target_dir: Optional[str] = None) -> Dict[str, Any]:
    agent = UIBuilderAgent(router=None)
    return await agent.scaffold(prompt, target_dir=target_dir)
