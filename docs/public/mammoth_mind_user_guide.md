# Mammoth Mind User Guide

This guide is published content. The MammothOS Guide (`/guide`) answers from it, so keep it accurate and free of internal details.

## What Mammoth Mind is

Mammoth Mind is the MammothOS chat workspace. You pick an agent lane, optionally pick a repository, and ask for help with planning, debugging, coding, or learning.

Mammoth Mind adapts its response style to the request: simple asks get a brief, natural reply; multi-part, technical, or explicitly thorough asks get a structured answer when that structure helps. It can explain its rationale and evidence without exposing private chain-of-thought.

Agent lanes:

- **Mammoth Assistant**: general planning, debugging, and product thinking.
- **Coding Agent**: repo-focused coding help and patch strategy.
- **Reasoning Agent**: decisions, tradeoffs, and next steps.
- **MammothOS Guide**: how to use MammothOS, ATLAS, and the SDKs.

You can reach Mammoth Mind two ways: the full **Mammoth Mind** page in the sidebar, or the **Mammoth Mind** pill in the top-right header, next to notifications. The pill opens a quick panel. On learning pages it answers with lesson awareness, and **Full view →** takes you to the full page.

## Agent mode

Agent mode is on by default. Use the **Agent / Classic** toggle in the chat header to switch.

1. Mammoth Mind writes a short plan.
2. It calls tools: searching docs, reading files in your selected repository, or fetching a web page.
3. It answers using what it found.

The run appears above the answer as a collapsible **Worked · N tool calls** timeline. Reasoning lines are short summaries of what the agent is doing, not hidden internal thoughts.

- **Approvals:** proposing a change never modifies your repository. Anything that would run or change something pauses on an approval card. **Approve** continues; **Reject** tells the agent to work around it.
- **Stop:** while a run is active, the Send button turns into **Stop**.
- **Incomplete or failed:** a response-format failure is not automatically an output cutoff. The runtime retries once where appropriate and keeps saved work. It does not label an offline, malformed, or interrupted-by-output-limit response as completed.
- **Continue task:** eligible unfinished runs offer this action in Mammoth Mind and the Coding workspace. It retains saved work and your original request, rather than making you repeat the prompt. It uses additional model credits and permits up to two continuations; access and approvals still apply.
- **Diagnostics:** expand the timeline, then Model call diagnostics for the provider/model, reported completion reason, and token usage. Missing usage is labeled not reported. These details are not a factual-accuracy guarantee.
- **Decision protocol:** diagnostics show whether a call used schema-constrained output, JSON mode, or the text compatibility path. Supported providers get stricter decision formatting; every tool still passes the platform's argument, access, and approval checks.
- **Classic path:** slash commands and messages with attachments use classic chat automatically.

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

ATLAS is the adaptive tutor. It keeps your lesson progress, coaches you on exercises, and can be embedded in other products through the ATLAS FAB SDK. In MammothOS itself, the tutor is reached through the Mammoth Mind header pill.

How a lesson works:
- **Lesson card.** Each lesson shows what to know first, sample input, expected output, and how you know you're done. These come from the lesson itself, so sections with no data are hidden.
- **Stuck detection.** If you fail three times in a row, hit the same error twice, or go 20 minutes without progress, a "sticky step" note appears with one concrete next move.
- **Next.** Next checks that the current exercise has passed. If it hasn't, you can keep practicing or choose **Continue anyway**. Skipping is always your call.
