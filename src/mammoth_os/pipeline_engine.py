class PipelineEngine:
    """
    DAG-based task pipeline builder. Nodes are callable tasks; edges
    define data dependencies. Executes independent nodes in parallel.
    """

    def build_dag(self, tasks: list[dict]) -> dict:
        """
        Build a DAG from a task list.
        Each task: {"id": str, "fn": callable, "depends_on": list[str], "input": any}
        Returns adjacency structure.
        """
        graph = {}
        for task in tasks:
            graph[task["id"]] = {
                "fn": task["fn"],
                "depends_on": task.get("depends_on", []),
                "input": task.get("input"),
            }
        return graph

    async def execute(self, dag: dict) -> dict:
        """Execute the DAG, running independent nodes in parallel."""
        results = {}
        completed = set()
        pending = set(dag.keys())

        while pending:
            ready = [
                node_id for node_id in pending
                if all(dep in completed for dep in dag[node_id]["depends_on"])
            ]
            if not ready:
                raise RuntimeError("DAG cycle detected or unresolvable dependency.")
            futures = [dag[n]["fn"](dag[n].get("input")) for n in ready]
            node_results = await asyncio.gather(*futures, return_exceptions=True)# type: ignore
            for node_id, result in zip(ready, node_results):
                results[node_id] = result
                completed.add(node_id)
                pending.remove(node_id)
        return results

    def visualize(self, dag: dict) -> str:
        """Return a text-based DAG representation."""
        lines = []
        for node, data in dag.items():
            deps = " → ".join(data["depends_on"]) or "START"
            lines.append(f"[{deps}] → [{node}]")
        return "\n".join(lines)
