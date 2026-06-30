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
            "mode": "rewrite" | "tagline" | "caption",
            "tone": "rugged" | "calm" | "motivational"
        }
        """
        content = payload.get("content", "")
        mode = payload.get("mode", "rewrite")
        tone = payload.get("tone", "rugged")

        if mode == "tagline":
            result = self._generate_tagline(content)
        elif mode == "caption":
            result = self._generate_caption(content, tone)
        else:
            result = self._rewrite(content, tone)

        return {
            "agent": "brand_voice",
            "mode": mode,
            "tone": tone,
            "input": content,
            "output": result,
        }

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
