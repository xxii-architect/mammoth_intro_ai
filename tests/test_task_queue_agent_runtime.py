import asyncio

from mammoth_os.agent_registry import load_agent
from mammoth_os.agents.task_queue_agent import TaskQueueAgent


def test_task_queue_agent_persists_queue_across_instances(tmp_path):
    storage = tmp_path / "state"
    agent = TaskQueueAgent(router=None, storage_root=str(storage))

    task_id = asyncio.run(agent.enqueue({"title": "Build browser layer", "priority": 1, "details": {"source": "test"}}))
    status_before = agent.run({"action": "status"})
    assert status_before["queue_depth"] == 1
    assert status_before["next_task"]["task_id"] == task_id

    reloaded = TaskQueueAgent(router=None, storage_root=str(storage))
    status_after = reloaded.run({"action": "status"})
    assert status_after["queue_depth"] == 1
    assert status_after["next_task"]["title"] == "Build browser layer"

    dequeued = asyncio.run(reloaded.dequeue())
    assert dequeued["task_id"] == task_id
    complete_result = asyncio.run(reloaded.complete(task_id, {"status": "done"}))
    assert complete_result is None
    finished = reloaded.run({"action": "status"})
    assert finished["completed_count"] == 1


def test_task_queue_agent_is_loadable_from_registry():
    agent = load_agent("task_queue", None)
    assert isinstance(agent, TaskQueueAgent)
