class BaseAgent:
    def __init__(self, router):
        self.router = router

    def execute_action(self, action_type: str, target: str, details: dict):
        raise NotImplementedError("Agents must implement execute_action()")
