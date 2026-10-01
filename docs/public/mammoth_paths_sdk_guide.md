# Mammoth Paths Workspace SDK

This guide is published content. The MammothOS Guide (`/guide`) answers from it, so keep it accurate and free of internal details.

## What Mammoth Paths is

Mammoth Paths is the MammothOS **workspace SDK**. It lets developers put the MammothOS workspace inside their own software:

- **Mammoth Mind agent runs**: ask a question, watch the plan, tool calls, and proposed diffs stream in, and approve or reject risky steps.
- **Your repositories**: connect a public GitHub repository and use it as context. Changes come back as a patch and are never pushed.
- **Notes** and the **build log**: personal records stored for your account only.
- **Terminal**: available to the workspace owner only.

The name has two meanings: the file paths in your code, and the path the guide walks with you.

Mammoth Paths is separate from the **Mammoth Mind tutor SDK** (formerly ATLAS FAB), which embeds adaptive lessons and tutoring.

## Packages

- Python: `from mammoth_os import MammothPaths`
- JavaScript: `@mammothos/paths` (no dependencies; works in browsers and Node 18+)

## Privacy model

- Every request is tied to your sign-in. You only ever see your own runs, repositories, notes, and build log.
- No repository selected means no repository context.
- The MammothOS platform repository is never available to customers.
- Notes and the build log need a Pro plan or higher.

## Approvals

Read-only tools run automatically. Anything that would run a command or change something pauses with an approval request. In the SDK you can supply an approval policy, or leave the run paused and decide later.

## Usage metering

Both clients accept a usage hook that reports each call (surface, status, duration) so you can meter usage in your own product.
