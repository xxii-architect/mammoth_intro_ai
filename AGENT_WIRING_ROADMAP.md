# Agent wiring roadmap

## Goal
Get every major agent from the MammothOS registry into a visible, understandable workflow with real backend-backed module state instead of static "idle" cards.

## Phase 1 — make the registry visible
- Use `src/mammoth_os/agent_registry.py` as the canonical source of truth.
- Expose each registered agent through `/api/modules` and `/api/agents`.
- Replace hard-coded `idle` statuses with backend-derived state such as `active`, `ready`, `loading`, or `error`.

## Phase 2 — wire the workflow
- Ensure each agent is reachable by the runtime router.
- Add explicit workflow metadata:
  - `workflow_ready`: true when the agent is routed into plan/execute or task execution.
  - `workflow_stage`: `registered`, `routed`, or `autonomous`.
- Keep the plan/execute workflow and the Modules page in sync.

## Phase 3 — give the UI a real story
- Show the backend status, workflow stage, and capabilities for each module card.
- Make the Modules page read from the backend rather than local toggles alone.
- Surface whether an agent is available, active, or still waiting for runtime wiring.

## Phase 4 — harden observability
- Log agent task starts/completions through the existing activity and task flows.
- Add health and heartbeat signals so module cards can move from `ready` to `active` automatically.
- Add approval-aware paths for agents that mutate files or state.

## Phase 5 — expand autonomous capability
- Connect the coding, research, reflection, field ops, and custodial agents to richer task orchestration.
- Progress from single-agent runs to multi-agent plan/execute pipelines.
- Add a dedicated “autonomous agent runs” panel once the core registry is stable.

## Estimated credit usage by phase
- Phase 1 — registry + visibility: low (~1-2% of a monthly budget) because it is mostly backend/UI wiring and focused validation.
- Phase 2 — workflow routing: low-to-medium (~2-3%) because it touches runtime maps, plan steps, and agent entrypoints.
- Phase 3 — UI story + observability: low (~1-2%) when done as targeted card/status improvements.
- Phase 4 — health signals + approvals hardening: medium (~2-3%) because it usually needs iterative runtime testing.
- Phase 5 — deeper autonomous orchestration: medium-to-high (~3-5%) depending on how many agents are upgraded in one pass.

## Current focus
- Keep the registry-backed module payload and observability slices stable.
- Expand approval-aware execution to non-coding ATLAS state mutation operations.
- Use the autonomous run contract (`/api/autonomous/runs`) to drive Phase 5 run panels and orchestration UX.
- Continue promoting routed agents into deeper autonomous profiles with explicit rollback/safety checkpoints.
