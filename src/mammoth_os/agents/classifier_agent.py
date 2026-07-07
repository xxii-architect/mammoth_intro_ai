class ClassifierAgent(BaseAgent):# type: ignore
    """
    Classifies incoming requests and events into intents, routes them to
    the correct agent, and tags them with structured metadata labels.
    """

    async def classify(self, text: str) -> dict:
        """
        Classify input text into intent and routing decision.

        Returns:
            {
                "intent": str,
                "target_agent": str,
                "confidence": float,
                "labels": list[str],
                "routing": dict,
            }
        """
        ...

    async def route(self, classification: dict) -> str:
        """Return the target agent_id based on classification."""
        return classification.get("target_agent", "orchestrator_agent")

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "CLASSIFY_REQUEST":
            result = await self.classify(event.payload.get("text", ""))
            await self.emit_event("CLASSIFY_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "ClassifierAgent shutting down.")