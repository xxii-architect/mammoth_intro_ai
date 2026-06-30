"""
Mammoth OS — VisualEngineAgent
Generates structured visual concepts, crayon‑sketch prompts, and brand‑aligned
illustration descriptions for True XXII Supply and Mammoth OS.
"""

from typing import Dict, Any
from datetime import datetime


class VisualEngineAgent:
    """
    Produces visual concepts in the True XXII Supply art style.
    Includes crayon‑sketch aesthetic and compass‑rose brand signature.
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected payload:
        {
            "subject": "pine tree",
            "style": "crayon" | "sketch" | "diagram",
            "mood": "calm" | "rugged" | "bright",
            "include_compass": True | False
        }
        """
        subject = payload.get("subject", "outdoor scene")
        style = payload.get("style", "crayon")
        mood = payload.get("mood", "rugged")
        include_compass = payload.get("include_compass", True)

        concept = self._generate_concept(subject, style, mood)
        palette = self._generate_palette(mood)
        compass = self._generate_compass() if include_compass else None

        return {
            "agent": "visual_engine",
            "timestamp": datetime.utcnow().isoformat(),
            "subject": subject,
            "style": style,
            "mood": mood,
            "concept": concept,
            "palette": palette,
            "compass_rose": compass,
        }

    # ---------------------------------------------------------
    # INTERNAL GENERATORS
    # ---------------------------------------------------------

    def _generate_concept(self, subject: str, style: str, mood: str) -> str:
        """
        Creates the core visual description.
        """
        base = f"A {style}-style illustration of {subject}"

        if style == "crayon":
            base += (
                ", drawn with soft, uneven strokes and a hand‑made feel. "
                "Edges are imperfect, giving it a warm, human texture."
            )
        elif style == "sketch":
            base += (
                ", rendered with quick pencil lines, light shading, and "
                "a field‑journal aesthetic."
            )
        elif style == "diagram":
            base += (
                ", labeled cleanly with simple callouts, like a survival field guide."
            )

        if mood == "calm":
            base += " The atmosphere feels quiet and peaceful."
        elif mood == "bright":
            base += " Colors feel energetic and optimistic."
        else:
            base += " The tone is rugged, outdoorsy, and grounded."

        return base

    def _generate_palette(self, mood: str) -> Dict[str, str]:
        """
        Suggests a color palette based on mood.
        """
        if mood == "calm":
            return {
                "primary": "soft pine green",
                "secondary": "warm beige",
                "accent": "muted sky blue",
            }

        if mood == "bright":
            return {
                "primary": "sunlit yellow",
                "secondary": "vibrant orange",
                "accent": "deep forest green",
            }

        return {
            "primary": "charcoal gray",
            "secondary": "earth brown",
            "accent": "pine green",
        }

    def _generate_compass(self) -> Dict[str, Any]:
        """
        Generates the True XXII Supply compass‑rose brand signature.
        """
        return {
            "style": "crayon",
            "position": "top-right corner",
            "design": {
                "points": 4,
                "north_label": "22",
                "needle_direction": "up",
                "line_weight": "thin",
            },
            "notes": "Matches True XXII Supply crayon-sketch brand watermark.",
        }
