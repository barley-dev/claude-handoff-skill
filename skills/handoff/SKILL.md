---
name: handoff
description: Use when the user wants to hand off the current conversation to a new session. Triggers include phrases like "handoff", "wrap up", "session end", "prepare handoff", "start handoff", or similar.
---

# Conversation Handoff

> **Version: v2 (2026-05-01)**

When the user triggers a handoff, execute the steps below in order. The goal is to let the next Claude session reconstruct the full working context from the handoff document alone — minimal back-and-forth with the user.

## Configuration

This skill reads user configuration (workspace root, handoff directory, optional template path, etc.) from the user's `CLAUDE.md`. See [`references/user-config.md`](references/user-config.md) for the required and optional variables and how users declare them.

If the user has not configured anything, defaults apply: workspace root is inferred from the conversation, handoff documents go to `<WORKSPACE_ROOT>/_handoffs/`, no template is used.

## Step 0: Get the current time

Before writing anything, get the precise current time:

```bash
date '+%Y-%m-%d %H:%M:%S %Z'
```

Use this timestamp for the filename and all time references in the document. Never estimate or guess.

## Step 0.5: When the AI suggests a handoff (vs user-triggered)

If the user explicitly triggered the handoff, skip this step and go to Step 0.7.

The underlying question for proactive suggestion is: **would continuing in this session cost the next session more than starting fresh?** The next session will need to reconstruct the working context — if that reconstruction cost is already approaching the cost of just writing it down explicitly, it is time to suggest a handoff.

The table below lists common signals as reference anchors. Treat them as heuristics, not rules. Combine multiple weak signals when judging; do not trigger on a single signal that contradicts the underlying question.

| Signal | Reference anchor | Why this signal | Action |
|--------|------------------|-----------------|--------|
| Topic shift | New topic unrelated to current work | A different topic means almost no shared context survives — better to start fresh | Suggest opening a new conversation (not a handoff) |
| Turn count + density | Around 15–20 turns combined with high information density | High-density turns accumulate state the next session must reconstruct; the cost grows superlinearly with turn count | Suggest a handoff |
| Turn count + task incomplete | Around 20+ turns with the task still in progress | At this length, the gap between "what was decided" and "what is in the conversation transcript" is wide enough that an explicit summary saves the next session significant time | Strongly recommend a handoff |
| Deliverable complete | A stage output is ready (file written, decision made, milestone reached) | Stage boundaries are natural compression points — handing off here lets the next session start from a clean state rather than mid-flight | Natural handoff point |
| Task complete + context shift | Next work is different in nature (e.g. design → execution) | Different work types need different mental models; carrying the previous session's framing is friction, not help | Suggest `/clear` or a new conversation |
| Context growth rate | Each turn produces large output that keeps growing | If output volume per turn is increasing, the session is accumulating state faster than it is consolidating — a handoff before the curve gets steeper is cheaper than after | Prepare for handoff proactively |

What "high information density" looks like in practice: multiple file edits, dense decision-making, accumulated context the next session would need to reconstruct, or several rounds of tool-result interpretation. Low density: short Q&A, quick lookups, single-file simple edits.

**Make the exit condition explicit.** When suggesting a handoff, confirm with the user where the current session should stop ("what counts as done for this handoff?"). When the user triggers the handoff manually, infer the exit condition from context and write it into the frontmatter without asking.

**Don't use "context is full" as the signal.** With long context windows, raw token count is no longer a reliable cue. Use turn count, information density, and topic coherence instead.

> **Observation note (Opus 4.7).** Opus 4.7 triggers tools less proactively than 4.6 (per Anthropic's Best Practices). Whether this affects proactive *suggestion* of handoffs (which is text output, not a tool call) is being evaluated. If you find the model never suggests a handoff in long sessions, or suggests too eagerly, mention it so this step can be tuned.

## Step 0.7: First-run setup check

Only run this step **after the handoff is confirmed to proceed** — user-triggered, or AI-suggested and user agreed. If Step 0.5 ended with the user choosing `/clear` or a new conversation instead, skip this step.

Check whether the user has configured this skill by grepping their `CLAUDE.md` files for the declaration form `^...WORKSPACE_ROOT:` (see [`references/first-run-setup.md`](references/first-run-setup.md) for the exact command and file-resolution logic).

- **Configured** → proceed to Step 1 directly.
- **Not configured** → offer the user two options: walk-through setup (three questions, then a paste-ready snippet) or use defaults (infer workspace root and save to `<workspace>/_handoffs/`). Either path lets the current handoff continue in the same turn.

The skill never edits `CLAUDE.md` directly. It produces a snippet and asks the user to paste it themselves.

## Step 1: Detect environment and save location

Do NOT ask the user what environment they are in. Detect it by checking which tools are available:

| Environment | Detection | Save strategy |
|-------------|-----------|---------------|
| Desktop app with MCP | Filesystem tools or `osascript` available | Write directly via MCP or osascript |
| Web / mobile app (with compute) | No Filesystem tools, but bash / create_file available | Create a downloadable `.md` in the output area |
| Web / mobile app (no compute) | Neither Filesystem nor bash available | Output full content in a code block for copy-paste |
| CLI / terminal agent | Local filesystem access | Write directly to the filesystem |

**Save location**: under `HANDOFF_DIR` as declared in user config (default: `<WORKSPACE_ROOT>/_handoffs/`). If the directory does not exist, create it.

For environments without filesystem access, tell the user:
1. The suggested filename: `Handoff_{YYYY-MM-DD}_{short-topic}.md`
2. Where to save it: `<HANDOFF_DIR>` on their machine

## Step 2: Determine handoff type

Scan the conversation and pick one:

- **Type A — conversational handoff (default).** Planning, design, writing, file organization, research discussion, etc.
- **Type B — code task handoff.** The conversation produced an actionable task for another agent to execute (code change, script, batch operation). Type B needs explicit objectives, current state, and verifiable acceptance criteria. See [`references/type-b-structure.md`](references/type-b-structure.md).

## Step 2.5: Determine audience

Handoff is **active compression** — rewriting the current conversation into the minimum form the *next reader* needs. The reader's identity matters.

| Audience | When | Writing style |
|----------|------|---------------|
| `model` (default) | Next session is another Claude / LLM picking up the work | Dense, structured, token-efficient; skip motivational prose; use short tags and bullets; causal chains via `→` are fine |
| `human` | User explicitly says the handoff is for a person to read (themselves, a colleague, a collaborator) | Full sentences, narrative flow, explicit rationale, avoid shorthand and model-oriented jargon |

**Detection**: default to `model`. Switch to `human` when the user's trigger message says so — e.g. "this is for me to read later", "handoff for <person-name>", "I want to print this", "write it so a person can understand". If unsure, ask once.

Write the chosen audience into the frontmatter (`audience: model` or `audience: human`) so any future reader knows which writing style is in effect.

## Step 3: Resolve all paths

Every path written to the handoff document must start with `~/` or be an unambiguous absolute path. This is the single most important correctness constraint of the skill. See [`references/path-resolution.md`](references/path-resolution.md).

## Step 4: Create the handoff document

### 4a — With template and Filesystem access

If the user has `TEMPLATE_PATH` configured AND Filesystem MCP is available, use the template-based flow for speed and accuracy. See [`references/template-workflow.md`](references/template-workflow.md).

### 4b — Without template

Generate the document inline using the structure below.

### 4c — Core document structure

Every handoff document has these core sections:

```markdown
---
date: YYYY-MM-DD
topic: Project name
workspace: ~/full/path/to/workspace/
exit_condition: [complete / interrupted / branched] — one-line description
type: handoff
audience: model           # "model" (default) or "human" — see "Audience" section below
prev: ~/...previous-handoff-path (omit line if none)
---

> **Document location:** ~/full/path/to/HANDOFF_DIR/Handoff_YYYY-MM-DD_slug.md

# [Project name] — Handoff YYYY-MM-DD

## Workspace root
`~/full/path/to/workspace/`

## Completed in this session
(Each item: "problem / context → finding / conclusion → action taken")
(Causal chain, not just a list — so the next session understands why, not only what)
(All paths in full `~/...` form)

## Pending / to-do
(Grouped by deadline or time frame, e.g. "### Before 3/14 (3/20 departure deadline)")
(Each item: why this deadline — so the next session can judge urgency)
(Flag dependencies: which items must precede others)
(For open-ended tasks with no hard deadline, state the relative priority instead)
(**Attach one line per item: what "done" looks like** — which file will exist, containing what. See "Deliverable clause")

## Key decisions and rationale
(Record judgments made and why)
(Include "alternatives considered but rejected" — prevents the next session from re-exploring dead ends)

## File changes
- Created: `~/...`
- Modified: `~/...`
- Deleted: `~/...`
```

### 4d — Optional sections

Append optional sections based on context. See [`references/optional-sections.md`](references/optional-sections.md) for the decision rules and templates. Typical additions include a key-files quick reference, cross-workspace links, a schedule, or verification anchors.

### 4e — Type B additional sections

For Type B handoffs, insert task-specific sections (objectives, current code, acceptance criteria, out-of-scope) between the core structure and optional sections. See [`references/type-b-structure.md`](references/type-b-structure.md).

### 4f — Action tracker sync (opt-in)

If the user has `ACTION_TRACKER` configured, sync the handoff's completed and pending items to the tracker file. See [`references/action-tracker-sync.md`](references/action-tracker-sync.md). Skip this step if `ACTION_TRACKER` is not set.

## Writing principles

The primary reader of a handoff document is the next Claude session. Design for minimum-token reconstruction of working context.

- **Make the causal chain explicit.** Record not just "what was done" but "why this way" and "what was considered but rejected." The biggest time-waster for the receiving session is re-walking dead ends.
- **All paths self-contained.** Every path in `~/...` form. The receiving session has zero context about directory structure; any path that requires guessing is a waste.
- **Make time pressure and dependencies explicit.** Group pending items by deadline with a reason attached, so the next session can judge priority without relying on vague "high / medium / low" labels.
- **Use the actual timestamp from Step 0.** Never estimate.
- **Deliverable clause.** Attach to each pending item one line saying what "done" looks like — which file will exist, containing what. E.g. "when done, `_wiki/X.md` exists and contains an 'acceptance criteria' section."

  > **Why** (established 2026-08-29, from a verification sweep of 8 old handoff messages): without a stated deliverable, no one can tell a month later whether the item was finished. Of the 8 checked, 5 of the 6 judged "already done" were wrong — the judge had no standard for what "done" should look like, so proxy signals were used instead (a later handoff exists in the same workspace, a `_wiki` page says "landed", a README has a version section). All three proxies fail in the same direction: they turn unfinished work into "finished."
  >
  > The single item that could be judged "definitely not landed" was the one whose SPEC had written acceptance criteria — one `grep` settled it. **One line now buys mechanical verifiability later.**
  >
  > See [[false-completion-signals]].

## Step 5: Generate and present the handoff message

After writing the handoff document, output the handoff message as a standalone paragraph in the chat. The user copy-pastes this message to start the next session — they should not have to open the handoff file to find it.

### Output rules

Output the handoff message as plain text — no blockquote prefix (`>`), no code-block fence (triple backticks) — separated from surrounding text with blank lines above and below. This ensures the user's clipboard captures only the message content; in many markdown renderers blockquote and code-block prefixes get copied along with the text and pollute the pasted message.

### Handoff message templates

(The code blocks below are for template demonstration only. When outputting the actual handoff message to the chat, remove the code block wrapper and deliver as plain-text paragraph.)

**Desktop / local (handoff file already on the user's machine):**

```
I am continuing work on [project name]. Please read the handoff document below first — it contains the background, completed items, and pending tasks:

[full ~/... path to the handoff document]

Workspace root: [~/... full path]

Current state: [one-line summary of status and next step]
Exit condition: [complete / interrupted / branched — exit condition]
Suggested model: [optional, see "Suggested model field" below]
```

**Web / mobile (handoff file needs manual upload):**

```
I am continuing work on [project name]. I have a handoff document to share.

Please read the attached file (Handoff_YYYY-MM-DD_slug.md) first — it contains the background, completed items, and pending tasks.

Workspace root: [~/... full path]

Current state: [one-line summary of status and next step]
Exit condition: [complete / interrupted / branched — exit condition]
Suggested model: [optional, see "Suggested model field" below]
```

**Type B (code task handoff):**

```
[One-sentence task description]. Please read the task handoff document below — it contains the objective, current logic, and acceptance criteria:

[full ~/... path to the handoff document]

Workspace root: [~/... full path]

Key changes: [list the main change points so the receiving agent knows the scope]
Exit condition: [complete / interrupted / branched — exit condition]
Suggested model: [optional, see "Suggested model field" below]
```

### Suggested model field (optional)

Purpose: when the handoff is consumed, the next session sees the model routing recommendation without having to consult CLAUDE.md routing rules.

Fill rule (pick one; **omit the line entirely if none applies**):

- **Single-stage task**: list the model directly, e.g. `Opus (proposal writing)` or `Sonnet (document conversion)`
- **Multi-stage with different models per stage**: list per stage, e.g.
  ```
  Suggested model:
    - Stage 1 (document digestion): Sonnet
    - Stage 2 (folder restructure): Opus
    - Stage 3 (main draft): Opus
  ```
- **Task aligns with workspace CLAUDE.md routing**: write "per project rules", e.g. `per ~/path/to/workspace/CLAUDE.md model selection`
- **No useful routing recommendation**: omit the line, do not write a placeholder like "no recommendation"

Decision basis: the user's global CLAUDE.md "model selection" section, the workspace CLAUDE.md "model selection" section, and the `task-dispatch` skill. The routing rules themselves stay in CLAUDE.md as the single source of truth; this field is only "the result of applying those rules to the current handoff."

### Principles for the message

- First line names the project
- Both the handoff path and the workspace root use full `~/...` form
- If the file is not on the user's machine, remind them to upload or save it first
- One sentence summarizes current state and suggested next step
- If there is an `INDEX.md` or other navigation file, mention its full path
- Keep the whole message under ~8 lines by default; if the multi-stage **Suggested model** block is needed, allow up to ~12 lines
- The **Suggested model** field is included only when it provides useful routing; omit the line entirely if not (do not write a placeholder)

## Step 5.5: Append the handoff message to the central file (required, never skip)

After printing the handoff message to the conversation, append it — **in the same turn** — to the central handoff-message file. The user should never have to paste it manually.

**Target file**: `~/資料/_harness/交接語/OPEN.md`

> This path is fixed and does not follow the workspace. `~/資料` maps to each machine's iCloud path via `$CLAUDE_DATA_ROOT`; always write it as `~/資料/`, never hard-code a machine-specific absolute path.
> If the file does not exist (new machine, or the user has not set it up), run `mkdir -p ~/資料/_harness/交接語/已啟動`, create the OPEN.md skeleton, then append.

**Entry format** (append at end of file):

```markdown
## [YYYY-MM-DD HH:MM] <project name>

| | |
|---|---|
| 狀態 | 待啟動 |
| 工作區 | `~/...` |
| 交接文件 | `~/.../Handoff_YYYY-MM-DD_slug.md` |
| 結束狀態 | 完成／中斷／分支 — <exit_condition> |

### 交接語

<full handoff message, plain text, verbatim identical to what Step 5 printed>

---
```

> Keep the table labels and the `### 交接語` heading in Chinese even in this English variant — the user reads one shared file, and mixed headings would break scanning.

**Rules**:

- Use the real timestamp from Step 0; never estimate
- **The 狀態 field is not always `待啟動`.** Three values:
  - `待啟動` — ready to start now
  - `待啟動` plus a separate `| 期限 | <date> |` row — when time-critical, the deadline gets **its own row**, never the status field
  - `⏸ 前置條件未成熟——現在不要做` — add a `| 前置 | <condition> |` row saying what it waits on
  Mixing these makes the user assume everything is actionable now (found in live use, 2026-08-27)
- **Deadlines carry a date only — never a countdown, never a symbol** (user's ruling, 2026-08-29: "keep the deadline, drop the countdown")
  - ✅ `| 期限 | 9/07 送件 |`
  - ❌ `| 狀態 | 🔴 待啟動 ⏰ 9/07 deadline, 10 days left |`
  > **Why**: "10 days left" is a static value computed at write time — read it tomorrow and it is simply wrong. **A hard-coded date never rots; a hard-coded countdown always does.** Symbols (⏰🔴) turn a resident document into an alarm, violating rule 1 of the cognitive-load discipline in `~/.claude/CLAUDE.md` ("deadlines are placed, not pushed"): OPEN.md is a clock the user consults, not an alarm that interrupts him.
  >
  > **Known gap (not caused by this rule)**: the user has time blindness — seeing "9/07" does not convert itself into "how long do I have." The real fix is a small tool that computes the countdown live from the 期限 field, **not yet built**. Until then, give less rather than give it wrong.
- When entries interlock (A landing satisfies B's precondition), add a `| 連動 | <note> |` row cross-referencing them
- **Never record line counts or file sizes in the fields.** They go stale as files change and the user never reads them when copying a message (observed 2026-08-27: an entry went from 354 to 365 lines). The path is the stable identifier
  > The same test applies inside handoff documents citing other files: **ask whether the line count is load-bearing for this judgement** — omit it when it merely describes size, keep it when it carries the argument (e.g. "at 354 lines this needs splitting")
- The message must be **verbatim identical** to what Step 5 printed — copying from the file and copying from the conversation must yield the same text
- **Append, never overwrite.** OPEN.md is an accumulating file and must never be rewritten wholesale
- If one handoff produces several documents (interleaved projects), append **one entry per document**
- After appending, state the path in one line, e.g. `交接語已寫入 ~/資料/_harness/交接語/OPEN.md`. Do not dump the file contents
- If the write fails (missing path that cannot be created, permission error), **say so explicitly** and tell the user to save the message manually — never fail silently

### Retirement check (after appending, same turn)

**Only check existing entries for the same workspace.** Do not scan the whole file or do a general tidy-up.

1. After appending, `grep` OPEN.md for other entries whose `| 工作區 |` matches this one
2. For each, ask one question: **does this handoff supersede it?** (later progress on the same work line → yes; same workspace but a different task → no)
3. For those superseded, cut the whole entry to `~/資料/_harness/交接語/已啟動/YYYY-MM.md` (create the month file if absent) and prefix it with `## 退場理由：<one line>`
4. If unsure, **leave it alone** and ask the user in one line: "OPEN.md still has an entry <title> — does this handoff supersede it?"

**Retire only what this handoff supersedes.** Other stale entries (things the user finished themselves, external events that vanished) are out of scope — that remains a dedicated session's job.

> **Why this was added** (2026-08-29): this section previously said "do not judge whether older entries have gone stale," and the result was a file with an intake but no outlet — `已啟動/` was **completely empty** since its creation on 8/27, with all 13 entries piled in OPEN.md, 4 of them long superseded yet still marked "待啟動". The user's words: "there doesn't seem to be any automatic update mechanism when writing a handoff… if work stops halfway before a formal handoff, OPEN.md doesn't update itself, which gets awkward."
>
> The moment of writing is the **only** time it is knowable which entry this one supersedes — the superseded entry's context is still in the conversation. Miss it and only an after-the-fact sweep can recover it. The old rule deferred that judgment to "a dedicated session," and that session did not happen for two days.

**Still do not**:

- Deduplicate or re-sort OPEN.md as a whole
- Delete any entry (retiring means **cutting to** `已啟動/`, not deleting)
- Judge staleness of entries this handoff does not supersede
- Mirror the message anywhere else (`_monitoring/_handoffs/INDEX.md` indexes handoff **documents**, not messages)

## Notes

- If the conversation covered multiple projects, write a separate handoff document for each
- If a handoff for the same topic and date already exists, update it rather than creating a new one
- **Already-decided next steps are executed directly.** If the handoff or user instruction specifies the next step, the AI proceeds to that step after finishing the current one, without inserting a confirmation question
- **Time-sensitive operations.** When the work involves schedules, reminders, deadlines, or "what's good to do now," always run `date` first to get precise current time — never estimate
- **Self-contained principle.** The handoff document should let the next session resume work without needing the chat history. Objectives, completed items, output paths, next-step commands, and the handoff message itself — all present, all explicit

## Related skill: save-conversation

This skill performs **active compression** — selecting and restructuring conversation content for the next task. It deliberately drops anything not needed going forward.

If the user also wants to preserve the **raw, unabridged transcript** of the conversation, that is a separate concern handled by the `save-conversation` skill. The two are complementary:

- `handoff` → compressed, forward-looking, read by the next session
- `save-conversation` → raw archive, retrospective reference, read by humans when needed

Both can be invoked in the same session. Running them in order (`handoff` first, then `save-conversation`) produces both artifacts without interfering.
