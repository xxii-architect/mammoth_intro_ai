"""
Mammoth OS — BrandVoiceAgent
Applies the True XXII Supply brand voice: rugged, empowering, outdoors-minded,
and grounded in the 'Plant the Seed' philosophy and survival aesthetic.
"""

from typing import Dict, Any


class BrandVoiceAgent:
    """
    Rewrites or generates content in the True XXII Supply brand voice.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "content": "text to rewrite",
            "mode": "rewrite" | "tagline" | "caption" | "stakeholder_summary" | "tutorial_copy" | "rewrite_with_constraints",
            "tone": "rugged" | "calm" | "motivational",
            "audience": "stakeholder" | "learner" | "operator",
            "constraints": ["..."],
            "output_format": "markdown" | "plain"
        }
        """
        if not isinstance(payload, dict):
            payload = {"content": str(payload or ""), "mode": "rewrite", "tone": "rugged"}

        content = str(payload.get("content") or payload.get("prompt") or payload.get("text") or "").strip()
        mode = str(payload.get("mode", "rewrite") or "rewrite").strip()
        tone = str(payload.get("tone", "rugged") or "rugged").strip()
        audience = str(payload.get("audience", "general") or "general").strip()
        constraints = payload.get("constraints") or []
        if not isinstance(constraints, list):
            constraints = [str(constraints)] if str(constraints).strip() else []

        if mode == "tagline":
            result = self._generate_tagline(content)
        elif mode == "caption":
            result = self._generate_caption(content, tone)
        elif mode == "stakeholder_summary":
            result = self._stakeholder_summary(content, audience, tone, constraints)
        elif mode == "tutorial_copy":
            result = self._tutorial_copy(content, audience, tone)
        elif mode == "rewrite_with_constraints":
            result = self._rewrite_with_constraints(content, tone, audience, constraints)
        else:
            result = self._rewrite(content, tone)

        return {
            "agent": "brand_voice",
            "mode": mode,
            "tone": tone,
            "audience": audience,
            "input": content,
            "output": result,
        }

    def _stakeholder_summary(self, content: str, audience: str, tone: str, constraints: list[str]) -> str:
        if not content:
            return "No source content provided for a stakeholder summary. Add the objective, scope, and expected impact."
        guardrail_text = "\n- Guardrails: " + "; ".join(constraints) if constraints else "\n- Guardrails: keep scope tight and preserve approval-safe workflows"
        return (
            f"### What changed\n{content}\n\n"
            f"### Why it matters\nThis update strengthens the operator experience, reduces ambiguity, and keeps execution grounded in a clearer workflow.\n\n"
            f"### Guardrails\n- Audience: {audience}\n- Tone: {tone}{guardrail_text}"
        )

    def _tutorial_copy(self, content: str, audience: str, tone: str) -> str:
        if not content:
            return "Tutorial copy is ready once the task, user path, and expected actions are provided."
        return (
            f"### {audience.title()} walkthrough\n"
            f"{content}\n\n"
            f"1. Start with the goal and keep scope clear.\n"
            f"2. Use the tool that matches the task.\n"
            f"3. Review the output before approving changes.\n"
            f"4. Keep the workflow additive and safe."
        )

    def _rewrite_with_constraints(self, content: str, tone: str, audience: str, constraints: list[str]) -> str:
        if not content:
            return "No source content provided. Add the text you want rewritten and the constraints for the output."
        rule_text = "; ".join(constraints) if constraints else "keep it concise and grounded"
        return (
            f"{content.strip()}\n\n"
            f"Audience: {audience}. Tone: {tone}. Constraints: {rule_text}."
        )

    # ---------------------------------------------------------
    # INTERNAL GENERATORS
    # ---------------------------------------------------------

    def _rewrite(self, content: str, tone: str) -> str:
        """
        Rewrite content in the True XXII Supply brand voice.
        """
        base = (
            f"{content.strip()} "
            f"Stay equipped. Stay aware. Keep moving forward."
        )

        if tone == "motivational":
            return (
                f"{content.strip()} "
                f"Every step you take plants a seed for tomorrow. "
                f"Be equipped. Be skilled. Be ready."
            )

        if tone == "calm":
            return (
                f"{content.strip()} "
                f"Slow down, breathe, and trust your training. "
                f"Even small steps plant the seed."
            )

        return (
            f"{content.strip()} "
            f"Don’t get caught running with scissors. "
            f"Stand your ground. Build your skills. Feel more alive than ever."
        )

    def _generate_tagline(self, theme: str) -> str:
        """
        Generate a rugged tagline based on a theme.
        """
        return (
            f"{theme.strip().title()}. "
            f"Be equipped. Be skilled. Be ready."
        )

    def _generate_caption(self, content: str, tone: str) -> str:
        """
        Generate a short caption for social posts.
        """
        if tone == "motivational":
            return (
                f"{content.strip()} — Plant the seed today. "
                f"Even the smallest habit grows into strength."
            )

        if tone == "calm":
            return (
                f"{content.strip()} — A quiet moment to reset. "
                f"Preparation is peace."
            )

        return (
            f"{content.strip()} — Fire burning, music playing, "
            f"and you’re exactly where you need to be."
        )
