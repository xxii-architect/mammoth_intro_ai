# Mammoth Mind User Guide

This guide is published content. The MammothOS Guide (`/guide`) answers from it, so keep it accurate and free of internal details.

## What Mammoth Mind is

Mammoth Mind is the MammothOS chat workspace. You pick an agent lane, optionally pick a repository, and ask for help with planning, debugging, coding, or learning.

Agent lanes:

- **Mammoth Assistant**: general planning, debugging, and product thinking.
- **Coding Agent**: repo-focused coding help and patch strategy.
- **Reasoning Agent**: decisions, tradeoffs, and next steps.
- **MammothOS Guide**: how to use MammothOS, ATLAS, and the SDKs.

## Repository context

- No repository selected means the agents answer without code context.
- Connect your own public GitHub repository in the **Repo Context** panel by entering `owner/repo`. It is cloned into a private sandbox that only your account can use.
- Use the sync button to pull the latest default branch. Remove a repository to delete its sandbox copy.
- You can connect up to 5 repositories.
- Private repositories will be supported through the MammothOS GitHub App.

## Edits are proposals

When an agent changes code in a connected repository, MammothOS creates a local branch and returns a git patch. Apply it with `git am`, or open a pull request from it. MammothOS never pushes to your repository.

## Slash commands

- `/guide <question>`: ask the MammothOS Guide.
- `/plan <objective>`: create a step-by-step plan.
- `/agent <agent_id> <message>`: route a message to a specific agent.
- `/web <query>` and `/research <topic>`: internet-backed answers with sources.

## Reading the trace

Every run shows what the agents did, using one fixed set of labelled glyphs:

| Glyph | Meaning |
| --- | --- |
| Read / Searched / Fetched | The agent looked at code, search results, or a web page |
| Planned / Reasoning | The agent laid out steps or summarized its reasoning |
| Ran / Tool / Delegated | The agent executed a tool or handed work to another agent |
| Wrote / Proposed | The agent drafted a change for you to review |
| Awaiting approval | Nothing happens until you approve |
| Applied / Reverted / Failed | Final outcome of a change |

## ATLAS tutor

ATLAS is the adaptive tutor. It keeps your lesson progress, coaches you on exercises, and can be embedded in other products through the ATLAS FAB SDK.
