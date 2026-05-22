# Audit-Team Orchestrator (Antigravity)

When the user invokes the `audit-team` skill, you act as the Orchestrator for a deep multi-role audit.
Your job is to execute the audit by dynamically spawning 5 specialized subagents concurrently, waiting for their reports, and synthesizing an executive summary.

## Stage 1: Define Subagents
Read the role definitions from `skills/roles/`:
- `principal-engineer.md`
- `uiux-designer.md`
- `technical-writer.md`
- `test-engineer.md`
- `qa-engineer.md`

Use the `define_subagent` tool to register them dynamically for this conversation. The `system_prompt` for each must be the content of the markdown file, and you should also provide them the `severity-framework.md` and `blast-radius.md` as context if requested.

## Stage 2: Concurrent Deep-Dive
Use `invoke_subagent` to launch all 5 subagents CONCURRENTLY in a single tool call array.
Task each subagent to "Conduct your deep-dive audit of the project according to your role instructions."
Wait for all 5 to complete and return their findings.

## Stage 3: Synthesize Executive Summary
Read the template at `skills/templates/00-executive-audit.md` and `skills/templates/sprint-punchlist.md`.
Using the combined findings from all 5 subagents, fill out the Executive Summary and Punchlist.
Output the final Executive Summary to the user in a walkthrough artifact.
