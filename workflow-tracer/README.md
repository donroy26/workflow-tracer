# workflow-tracer

Companion to the `icm-architect` skill. Where that skill builds a workspace whose folders do the orchestration, this one tests the claim: give it a task, and it walks the tree cold the way an agent would, logging every file it opens and why, without doing the task. One self-contained HTML file draws the folder tree as a top-down bracket and overlays the route.

- `SKILL.md`: the procedure (tree, walk, done, report) and the walk rules.
- `scripts/tracer.py`: standard-library Python. `tree` scans the folder to `tree.json`; `read`, `scan`, `miss` append steps to `trace.jsonl` as the walk goes; `done` writes `trace.json` with totals and the four invariant checks; `html` bundles the page and both json files into `trace.html` (`tree` and `done` run it too).
- `assets/dashboard.html`: the page, as a fragment, styled to the Don's Bookshelf design system (tokens in `assets/brand/colors_and_type.css`, logo glyph and favicon beside it: cream paper, Lora, DM Sans, one spine accent per role). The brand has no dark palette, so the page's dark mode is the same room with the lights off: ink surfaces, cream text, the pastel spines as accents; it follows the system and a Dark/Light button overrides it. The credit line links donsbookshelf.com and the Clief Notes affiliate page. It takes its data from `window.TRACE_DATA` when inlined, else fetches `tree.json` and `trace.json` beside it. Folders fan out as a bracket; each folder's files stack under it in a drawer, pages as tall as they are heavy; everything off the route folds into one "N more" page; read files carry a step badge; the dashed line is the route; the right panel lists each step with layer, reason and cumulative tokens against the 8,000 budget. Play replays the walk. On a phone a Tree / Steps switch shows one panel at a time and the bracket pinch-zooms.
- `references/walker-brief.md`: the whole prompt the cold walker subagent receives.

Invoke: `/workflow-tracer [ROOT] <task>`.
