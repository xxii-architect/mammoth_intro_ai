class ReasoningEngine:
    """
    LLM inference wrapper with prompt chaining, token budget management,
    and response caching. Supports multiple model backends.
    """

    def __init__(self, config: dict):
        self.model_name = config.get("model_name", "gpt-4o")
        self.temperature = config.get("temperature", 0.2)
        self.max_tokens = config.get("max_tokens", 8192)
        self.timeout = config.get("timeout", 60)

    async def infer(self, prompt: str, system_prompt: str = None, **kwargs) -> dict:# type: ignore
        """Single inference call. Returns {text: str, tokens_used: int, model: str}."""
        ...

    async def chain(self, steps: list[dict]) -> list[str]:
        """
        Sequential prompt chain. Each step can reference prior outputs.
        steps: [{"prompt": str, "inject_prior": bool}, ...]
        """
        outputs = []
        for step in steps:
            p = step["prompt"]
            if step.get("inject_prior") and outputs:
                p = f"Prior result: {outputs[-1]}\n\n{p}"
            result = await self.infer(p)
            outputs.append(result["text"])
        return outputs

    async def summarize(self, text: str, max_words: int = 200) -> str:
        """Summarize long text to a target word count."""
        prompt = f"Summarize the following in {max_words} words or fewer:\n\n{text}"
        result = await self.infer(prompt)
        return result["text"]

    def token_count(self, text: str) -> int:
        """Estimate token count for budget management."""
        return len(text.split()) * 4 // 3  # Rough approximation