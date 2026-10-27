---
name: workflow-tracer
description: Dry-run a task against an ICM workspace, repo or vault and show the route the agent would take through the folder tree, without doing the task. Writes one self-contained HTML dashboard that draws the folder structure as a top-down bracket, then overlays every file read in order, with layer, reason, token cost and the ICM invariant checks. Use for "trace this task", "what would you read for X", "test the workflow", "test this ICM", "show me the route", "dry run", "walk it cold", "what context does X load", or to check a workspace built with icm-architect before trusting it.
license: MIT
---

# Workflow Tracer

A workspace built with `icm-architect` claims that folder structure does the orchestration: an agent given a task opens the entry file, follows the routing to one stage, reads that stage's contract and its named inputs, and stops, all under about 8,000 tokens. This skill tests that claim. A cold subagent gathers the context for a task exactly as an agent would and records every file it opens and why. It never does the task. The person watches the route on a bracket of the folder tree.

The walk is the one from icm-architect's walk test (entry file, then at most two more reads to the control point; load only what the step needs; every path must resolve). The layer definitions are in the table below; the `icm-architect` skill, if installed, has the long form.

## Invocation

`/workflow-tracer [ROOT] <task>`. ROOT is the workspace root (default: the working directory). The rest is the task to trace. If no task is given, ask for one in a line; a trace without a task is just a tree.

## Who does what

The **main session** draws the tree, opens the dashboard, briefs the walker, checks its log against its report, and writes the findings. It never walks. It is not cold: the harness has already loaded the entry file into it and it has usually read half the workspace, so its walk would show what it remembers rather than what the structure does to a fresh agent.

The **walker** is a subagent (`builder`, or a generic agent on `sonnet` at `medium` effort) that starts with nothing but the root, the task and the rules below. It reads, and it logs each read itself the moment it makes it. A log written afterwards from a summary loses the order, the line that sent it somewhere, and every scan it did without noticing.

## Procedure

Set `DIR` to a fresh folder in your scratchpad (`<scratchpad>/workflow-tracer`). `SK` is this skill's folder. Every command below is run through Bash with `python -I`.

**1. Draw the tree and open the dashboard first.**

```
python -I "$SK/scripts/tracer.py" tree "<ROOT>" -d "$DIR"
```

This writes `tree.json`, an empty `trace.jsonl`, a pending `trace.json`, and `$DIR/trace.html`: the dashboard with both json files inlined, one file that opens from disk with no server. Open it for the person now (`start "" "$DIR/trace.html"` on Windows, `open` or `xdg-open` elsewhere) and give the full path in one line. The output is a file, not an artifact; never publish it.

**2. Spawn the walker.** One Agent call, `subagent_type: "builder"` (or `model: "sonnet"`, `effort: "medium"`). The brief is the text in [references/walker-brief.md](references/walker-brief.md) with `<ROOT>`, `<TASK>`, `<DIR>` and `<SK>` filled in. Nothing else: no hint of where the answer lives, no file names, no summary of the workspace. Wait for it to return.

**3. Check, close and rewrite.** Read `$DIR/trace.jsonl` and compare it with the walker's returned route. Any read it reports but did not log, or logged but did not report, is a finding. Then:

```
python -I "$SK/scripts/tracer.py" done -d "$DIR" --task "<task>" --finding "<one line>" --finding "<one line>"
```

It prints the four checks (control point within entry + 2 reads; contract plus inputs under 8,000 tokens; routed by the catalog, not by search; every path read exists) and rewrites `$DIR/trace.html`. Add a `--finding` for what the checks cannot see: a routing row that was ambiguous, a contract whose Inputs are missing or stale, a reference file far bigger than the contract needed, a fact found in two places, the walker's own notes. Open the rewritten file again (the browser does not reload it on its own). It now draws the route, numbers each read, and replays it step by step. `html -o <path>` writes a copy somewhere the person keeps, if asked; never inside the traced workspace.

**4. Report.** In the reply: the file's full path, the route as a short numbered list (file, layer, tokens), the four verdicts, the findings, and the one structural change that would most shorten the route, phrased the way icm-architect would fix it (move or split a file, add a routing row, name an input) rather than as a note to explain more. Do not do the task, and do not offer to.

## The layer test

The tree's colours come from file names (`CONTEXT.md` is a contract, `docs/` is factory) and only decorate the bracket. The layer on each logged read is assigned by the walker from the question the file answered, never from its name or folder, and that is what the checks use. The test:

| Layer | The file is... | Example in a repo with a `CLAUDE.md` map |
|---|---|---|
| L0 | the file you opened first because it is the entry | `CLAUDE.md` |
| L1 | a file whose only job was to send you to another file | `docs/architecture.md`, an index |
| L2 | the first file that told you what to do for *this* task. Exactly one. | `docs/pages/rail.md` |
| L3 | a file the L2 says to obey on every task, whatever the task | `conventions.md`, `theme.md` |
| L4 | the material the task would act on | `rail.js`, `theme.js` |

- A file that both routes and instructs gets the layer of the question that sent you there; its tokens count once.
- A file that is both reference and instruction is L2 if it was the first to say what to do, otherwise L3.
- If no file says what to do, there is no L2, the first check fails, and L4 is reached by scanning. That combination is the finding: the workspace has no control point for the task.

## What counts

- A read is a file the walker opened. A `Glob` or `Grep` is a scan. Reading a folder listing is not logged.
- A working input the contract names that the walker checked but did not open is logged `--named`: no tokens, a dashed outline on the bracket, a `named` tag in the list. The walker opens the first unit of work and names the rest; it is a dry run, not the batch.
- The harness injects the project's `CLAUDE.md` into subagents, so the walker never opens it. It logs it as read 1 anyway: the tokens were loaded. Everything else it happens to know is off limits until it reads it.
- A file read twice is logged twice; the dashboard shows both numbers on the node.
- A path that does not resolve is still logged (`exists: false`); the check fails and the node is marked missing.
- The budget check counts L2–L4 only, since routing files are read on every task; the total is shown beside it.
- Tokens are bytes/4. Good enough to see a budget blow, not a bill.
- A partial read (`--lines A-B`) is charged for the slice. The tree node still shows the whole file's weight; the step shows the slice and the range. In a codebase the unit of work is a symbol inside a file, so this is the only honest way to score a read of one function in a 5,000-line module.

## Reading the dashboard

Folders fan out sideways as a bracket; a folder's files stack under it in a drawer, read ones first, each page drawn as tall as it is heavy (about 1,000 tokens per 9px, capped at 120px), so a file that blows the budget looks like the brick it is. Everything off the route folds into one "N more" page per drawer (`Expand all` opens every drawer; click any folder to toggle). Read files carry an orange badge with their step number; the dashed route runs between consecutive reads. Each check chip at the top opens, on click, the rule it applies, what was measured, and the steps it was judged on (the budget chip lists the L2–L4 reads heaviest first). The step list on the right gives the layer, the reason and the cumulative L2–L4 tokens against the 8,000 budget. Scans and dead ends appear in the list in orange and red; they have no node. `Play` replays the walk; `←` `→` step it.

## Guardrails

- **Never do the task.** If the task asks for an edit, the trace ends at the contract that would make it. If the person wants the task done afterwards, that is a separate request without this skill.
- **Never fix the workspace during the trace.** A trace that found a dead end reports it; moving files mid-walk destroys the evidence.
- **Never walk in the main session**, even to "just check" the walker. If its result looks wrong, spawn a second walker, one tier up.
- **One trace, one task.** Comparing two tasks is two invocations and two dashboards.
- **Big trees:** `tree` folds folders past depth 7 and lists 60 children per folder (`--depth`, `--max-children` to change). Folded folders still show their file and token counts.
