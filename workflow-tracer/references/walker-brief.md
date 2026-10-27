# Walker brief

The main session fills in `<ROOT>`, `<TASK>`, `<DIR>` and `<SK>` and sends this, whole, as the Agent prompt. Nothing is added: no file names, no hints, no description of the workspace.

---

You are a fresh agent dropped into the workspace at `<ROOT>` and given this task:

> <TASK>

Do not do the task. Gather the context you would need to do it, exactly as you would if you were about to start, and stop at the point where you would begin the work. The point of this exercise is to see where the folder structure sends a cold agent, so take the route the files give you, in the order they give it, and do not plan ahead to make the route look clean.

**Log every file you open, the moment you open it, before you open the next one.** Use Bash:

```
python -I "<SK>/scripts/tracer.py" read "<path relative to ROOT>" -d "<DIR>" --layer L2 --why "<the line that sent you here, quoted>" --via "<the file that pointed>"
```

If the entry file (`CLAUDE.md` or `AGENTS.md`) is already in your context because the harness loaded it, log it first anyway as layer L0: its tokens were loaded. Anything else you happen to know is off limits until you read it.

When nothing routes you and you have to search, log that instead of hiding it:

```
python -I "<SK>/scripts/tracer.py" miss "<what you looked for>" -d "<DIR>" --why "<where it should have been>"
python -I "<SK>/scripts/tracer.py" scan "<the glob or grep you ran>" -d "<DIR>" --why "<why the catalog did not route>"
```

A `Glob` or `Grep` is a scan. A folder listing is not logged. A file you open twice is logged twice. If you open only part of a file (a line range, a slice around one symbol), say so with `--lines A-B` on the same command: the trace is charged for the slice, not the file. Log the range you actually read, not the range you meant to.

**The route.** Open the entry file at the root. Find the line or table row that matches the task and follow it. Keep following until you reach the file that tells you what to do for this task; then read the inputs it names: every-run reference material in full, and the files the task would act on. Stop at the point where the work would start.

**Working inputs (L4).** Open the first unit of work the contract names, as the step would. Every other working input or output location the contract names, including the rest of a batch, is checked but not opened: log each with `--named --layer L4 --why "named as input; not opened"`. Nothing is left unlogged: if the contract names it and you did not open it, it appears as named. If the contract names a working file by rule rather than by path (the oldest, the one marked pending), log the scan that found it, then log what you opened.

**Layers** are assigned by the question the file answered, not by its name or folder:

| Layer | The file is... |
|---|---|
| L0 | the file you opened first because it is the entry |
| L1 | a file whose only job was to send you to another file |
| L2 | the first file that told you what to do for *this* task. Exactly one. |
| L3 | a file the L2 says to obey on every task, whatever the task |
| L4 | the material the task would act on |

A file that both routes and instructs gets the layer of the question that sent you there. A file that is both reference and instruction is L2 if it was the first to say what to do, otherwise L3. If no file ever says what to do, there is no L2: say so, scan for the files the task would touch, and log those as L4.

**Commands.** A command the contract says to run (a script, a pipeline, a build) is not run and not logged as a read; the trace stops in front of it. Mention it in your return, with the file that would have run it.

**Do not** edit, move or create anything in the workspace, run any script or pipeline, draft any part of the task, or offer to.

**Return** under 300 words: the route as a numbered list (path, layer, one clause on why), the first moment you were unsure where to go next, and anything the structure made harder than it should have been. Report only what you logged.
