# src/mammoth_os/agents/brand_voice_agent.py

import os
from typing import Dict, Any

from .base_agent import BaseAgent


class BrandVoiceAgent(BaseAgent):
    """
    BrandVoiceAgent (Stylish, confident, creative)
    - Writes brand copy and taglines
    - Generates creative content
    - Overwrites brand files (approval-gated)
    - Creates brand directories (approval-gated)
    """

    name = "BrandVoiceAgent"

    def __init__(self, router):
        super().__init__(router)

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        if action_type == "write_content":
            return self._write_content(target, details)

        if action_type == "generate_copy":
            return self._generate_copy(target, details)

        if action_type == "overwrite_brand_file":
            return self._overwrite_brand_file(target, details)

        if action_type == "create_brand_directory":
            return self._create_brand_directory(target)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    # --- Core brand operations ---------------------------------------------

    def _write_content(self, target: str, details: Dict[str, Any]):
        """
        Write new brand content.
        details:
            - content: str (required)
        """
        content = details.get("content")
        if content is None:
            return {"status": "error", "reason": "Missing 'content' in details"}

        dirpath = os.path.dirname(target)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "write_content",
            "target": target,
        }

    def _generate_copy(self, target: str, details: Dict[str, Any]):
        """
        Generate brand copy or tagline.
        For now: simple placeholder.
        Later: integrate DeepSeek or your creative engine.
        """
        theme = details.get("theme", "True XXII Supply")
        tagline = f"Be equipped. Be skilled. Be ready. — {theme}"

        # Guard against empty dirname (e.g., target is "out.txt")
        dirpath = os.path.dirname(target)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(tagline)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "generate_copy",
            "target": target,
            "tagline": tagline,
        }

    def _overwrite_brand_file(self, target: str, details: Dict[str, Any]):
        """
        Overwrite existing brand file.
        Approval-gated by Cortex.
        """
        content = details.get("content")
        if content is None:
            return {"status": "error", "reason": "Missing 'content' in details"}

        if not os.path.exists(target):
            return {"status": "error", "reason": f"File not found: {target}"}

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "overwrite_brand_file",
            "target": target,
        }

    def _create_brand_directory(self, target: str):
        """
        Create a new brand directory.
        Approval-gated by Cortex.
        """
        if os.path.exists(target):
            return {"status": "exists", "target": target}

        os.makedirs(target, exist_ok=True)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "create_brand_directory",
            "target": target,
        }
