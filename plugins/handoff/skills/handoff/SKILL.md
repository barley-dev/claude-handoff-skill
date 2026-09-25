---
name: handoff
description: Use when the user wants to hand off the current conversation to a new session. Triggers include "handoff", "wrap up", "session end", "prepare handoff", "start handoff", and the Chinese equivalents "交接", "開始交接", "準備交接", "寫交接", "交接文件", "交接出去", "進行交接", "交接給下一個", "交接給下個對話去做", or similar phrases in any language.
---

# Conversation Handoff

> **Version: v3 (2026-09-03)** — merged the former `handoff` / `handoff-zh` pair into this single skill. The two differed only in prose language; all seven `references/` files were byte-identical (`diff` confirmed). A skill is a set of behavioral instructions for the model, not a user interface, so it needs no translated twin: output language is governed by the user's own `CLAUDE.md`, which is orthogonal to the process defined here.

When the user triggers a handoff, execute the steps below in order. The goal is to let the next Claude session reconstruct the full working context from the handoff document alone — minimal back-and-forth with the user.

**Output language**: write the handoff document and handoff message in the language the user works in (follow their `CLAUDE.md`; default to the conversation's language). This skill's own text is English because it instructs you, not the user. Field labels in the templates below are shown in Chinese where the user's existing files use Chinese — keep whatever the target file already uses rather than switching it.

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

> If the model never suggests a handoff in long sessions, or suggests one too eagerly, report it so this step can be tuned.

## Step 0.7: First-run setup check

Only run this step **after the handoff is confirmed to proceed** — user-triggered, or AI-suggested and user agreed. If Step 0.5 ended with the user choosing `/clear` or a new conversation instead, skip this step.

Check whether the user has configured this skill by grepping their `CLAUDE.md` files for the declaration form `^...WORKSPACE_ROOT:` (see [`references/first-run-setup.md`](references/first-run-setup.md) for the exact command and file-resolution logic).

- **Configured** → proceed to Step 1 directly.
- **Not configured** → offer the user two options: walk-through setup (three questions, then a paste-ready snippet) or use defaults (infer workspace root and save to `<workspace>/_handoffs/`). Either path lets the current handoff continue in the same turn.

The skill never edits `CLAUDE.md` directly. It produces a snippet and asks the user to paste it themselves.

At first run only, also mention session identifiers in passing — see [`references/session-identifier.md`](references/session-identifier.md). This is unrelated to `WORKSPACE_ROOT` and never blocks or gates the handoff; it is a one-time, skippable suggestion, not a setup question.

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

- **Before marking any existing todo as "done", pass the completion gate below.** This skill's deliverable clause governs *writing* (an acceptance standard for the future reader). Marking an existing todo as complete is *judging* — a different act with a stricter bar.

### The completion gate (built in — do not rely on the user's CLAUDE.md for this)

This gate is part of the skill because a handoff that misreports finished work is worse than no handoff: the next session skips real work on your word. If the user's own `CLAUDE.md` also defines a completion gate, theirs wins where stricter.

**Hard rule**: before recording anything as "done / landed / shipped / archivable", run `ls` or `grep` to confirm the artifact exists, **and paste the command and its output into the handoff**. A completion claim with no command output is not a judgment — it is a guess, and must not be written down as fact.

**Three signals that are never evidence of completion:**

| Signal | Why it fails |
|---|---|
| Chronology | "A later handoff exists in this workspace" proves only that the workspace is still alive |
| Self-declaration | A `_wiki` page saying "landed", a README version bump, a prior handoff's "complete" — all written *at the time of the claim*, not verified after the fact |
| Name clues | Filename, directory name, file size, mtime are clues *about* content, not the content itself |

**Existence is not completion.** After locating the artifact, confirm it carries no pending markers: "待確認", "待審", "尚未查證", "未經核准", "TODO", "⬜" (adapt to the user's language).

> **Why this is an execution gate, not a method**: the same error recurred three times in ten days for one user because the rule was written as knowledge — you had to first notice "I am making a completion judgment" to invoke it, and that self-awareness is exactly what goes missing when wrapping up in a hurry. Writing the command and output *into the artifact* makes a violation visible as a gap on the page (a verdict column with no evidence column), so the user can catch it without knowing the methodology.

## Step 5: Generate and present the handoff message

After writing the handoff document, output the handoff message as a standalone paragraph in the chat. The user copy-pastes this message to start the next session — they should not have to open the handoff file to find it.

### Output rules

**You MUST precede the handoff message with a one-line lead-in that says explicitly what it is and what to do with it.** Put the lead-in on its own line, then a blank line, then the handoff message itself.

The lead-in must convey three things: **this is the handoff message**, **copy it**, **paste it into a new conversation**. Wording may vary; the three information points may not. Examples:

- "Here's the handoff message — copy it and paste it into a new conversation to continue:"
- "Handoff message below. Copy and paste it into your next session:"

> **Why this is a hard rule** (established 2026-09-03): this skill previously said only "output the handoff message as a standalone paragraph," with no labeling requirement, while simultaneously banning blockquotes and code fences (see below). Together those produce a block of plain text with no visual boundary and no explanation.
>
> Daily users recognize it; **first-time users do not**. Reported in practice: a student could not tell what the trailing text was for. The handoff message is this skill's final deliverable — if the reader cannot identify it, the whole flow fails to land.
>
> The lead-in sits *outside* the handoff message, so it does not compromise the clean-clipboard rule below — the user still copies only the message body.

Output the handoff message **body** as plain text — no blockquote prefix (`>`), no code-block fence (triple backticks) — separated from surrounding text with blank lines above and below. This ensures the user's clipboard captures only the message content; in a terminal the user selects the text by hand, and blockquote or fence prefix characters get dragged into the selection and pollute the pasted message.

> **This differs from how the same message is stored in the pending file, and the difference is deliberate.** In the file it *is* fenced (Step 5.5, rule 2), because Obsidian renders a copy button on every code block — one click, clean text, no selecting. The terminal has no such button. Same content, two destinations, two mechanics: **unfenced in the chat, fenced in the file.** If a future reader thinks these contradict, they do not — check which destination the rule is about before changing either.

**Trailing boundary — you MUST close the message with an explicit end marker.** The lead-in opens the message; a matching line closes it. Put a blank line after the message body, then a short line on its own saying the handoff message ends there — e.g. `（交接語結束）` or `— end of handoff message —`, in the user's language.

Then, if anything follows, separate it with another blank line. Placing the handoff message as the last block of the reply is still preferable, but the end marker is required either way.

> **Why both ends are marked** (established 2026-09-04): the opening lead-in was added on 2026-09-03 because first-time readers could not tell what the trailing text was for. That fixed the *start* and left the *end* unmarked, so the reader still had to guess where to stop copying. The user hit exactly this: he could not tell whether to stop at `建議模型` or before `目前進度` — and he is the person who designed the format. **The answer is that the message runs through `建議模型`**, its last template line; anyone who has to infer that will sometimes infer it wrong, truncating the state the next session needs.
>
> This only affects the *chat* rendering. In the pending file the message sits inside a code fence, which supplies both boundaries and a copy button. A terminal cannot use a fence (the backticks get dragged into a hand-selection), so the boundary must be stated in words instead.
>
> The end marker sits **outside** the message body, so the clean-clipboard rule is unaffected.

### Handoff message templates

(The code blocks below are for template demonstration only. When outputting the actual handoff message to the chat, remove the code block wrapper and deliver as plain-text paragraph.)

**The message body ends at the `Suggested model` line** (or at `Exit condition` when that field is omitted). Everything through that line is part of what the user copies; the end marker goes on the next line, outside the body.

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

**Target file**: the value of `PENDING_FILE` from the user's config (see [`references/user-config.md`](references/user-config.md)). Default when undeclared: `<WORKSPACE_ROOT>/_harness/handoffs/pending.md`.

> This path is deliberately **not** workspace-relative at read time — it is one central queue shared by every workspace, so a user working across several projects still has a single place to look. Resolve it once from config; never hard-code a machine-specific absolute path (a path containing `/Users/<name>/` is always wrong here — write `~`-relative instead, since the same vault syncs across machines).
> If the file does not exist (first run, new machine, or never set up), run `mkdir -p "$(dirname "$PENDING_FILE")"/archive`, create the skeleton via [`references/pending-file-setup.md`](references/pending-file-setup.md), then append.

**Entry format** (append at end of file):

If `<PENDING_DIR>/_format.md` exists, **read it and follow it** — it is the authoritative entry format for that user's file, and it may have been revised since this skill was written. The template below is the fallback when no `_format.md` is present.

````markdown
## <project name — no date prefix>

| | |
|---|---|
| 建立 | YYYY-MM-DD HH:MM |
| 狀態 | 待啟動 |
| 工作區 | `~/...` |
| 交接文件 | `~/.../Handoff_YYYY-MM-DD_slug.md` |
| 結束狀態 | 完成／中斷／分支 — <exit_condition> |
| 完成長什麼樣 | <observable deliverable — see Step 4> |

### 交接語

```
<full handoff message, plain text, verbatim identical to what Step 5 printed>
```

---
````

**Two format rules that changed on 2026-09-03 — do not revert them:**

1. **The title carries no date prefix.** The timestamp goes in a `| 建立 |` row. Reason: the old `## [YYYY-MM-DD HH:MM] title` form spent 18 characters on information that contributes nothing to deciding what to work on, and it crowded out the title text that dependency-matching relies on.
2. **The handoff message is wrapped in a bare code fence** (no language tag). This **reverses** the earlier prohibition on code blocks in this file. The old reason — "many markdown renderers copy the fence prefix characters along with the text, polluting the pasted message" — assumed the user selects text by hand and hits Cmd+C. This user copies via the renderer's own copy button (Obsidian shows one at the top-right of every code block), which yields clean plain text. Use **no** language tag: handoff messages contain `~/` paths and shell commands, and a language tag makes the syntax highlighter recolor them.
   > The lead-in and the "don't use blockquote/code block" rule in **Step 5** still govern the *chat* output, where there is no copy button. Fenced in the file, unfenced in the chat.

**Field semantics** — when `_format.md` exists it is authoritative and the following is only a summary of it. Do not restate its field rules here; edit `_format.md` instead, so there is one place to change. The essentials, for the no-`_format.md` case:

- Use the real timestamp from Step 0 for `| 建立 |`; never estimate
- **`狀態` is not always "ready".** Distinguish *ready now* from *blocked*, and when blocked add a row naming the blocker. Mixing them makes the user assume everything is actionable now (found in live use, 2026-08-27)
- **A deadline gets its own row, carries a date only — never a countdown, never an alarm symbol.** "10 days left" is computed at write time and is wrong tomorrow: **a hard-coded date never rots; a hard-coded countdown always does.** Symbols turn a resident document into an alarm; this file is a clock the user consults, not an alarm that interrupts them (if the user's `CLAUDE.md` defines a cognitive-load discipline, follow theirs)
  > **Known gap, not caused by this rule**: a user with time blindness does not automatically convert "9/07" into "how long do I have." The real fix is computing the countdown live at read time, **not yet built**. Until then, give less rather than give it wrong.
- **Never record line counts or file sizes.** They go stale and the user does not read them when copying a message (observed 2026-08-27: an entry went 354 → 365 lines). The path is the stable identifier
  > The same test applies inside handoff documents citing other files: **is the line count load-bearing for the judgement?** Omit it when it merely describes size; keep it when it carries the argument ("at 354 lines this needs splitting")

**Write rules** (these belong to the skill, not to the format):

- The message must be **verbatim identical** to what Step 5 printed — copying from the file and copying from the conversation must yield the same text
- **Append, never overwrite.** The pending file is an accumulating file and must never be rewritten wholesale
- If one handoff produces several documents (interleaved projects), append **one entry per document**
- **After appending, verify the write and report the verification — not the intent.** Run a `grep` for the new entry's title in the pending file and paste the result. Only then state that it was written. Do not dump the file contents.

  ```bash
  LC_ALL=C grep -c "^## <the exact title you just appended>" "$PENDING_FILE"
  ```

  Expected output is `1`. If it is `0`, the append silently failed — say so explicitly and tell the user to save the message manually. If it is `2` or more, you appended a duplicate — stop and resolve it before continuing.

  > **Why the command and not just the sentence** (established 2026-09-04, at the user's request): "交接語已寫入 …" written on its own is a *self-declaration* — the same class of evidence this skill's completion gate rejects. The user reported that after each handoff he was opening `pending.md` himself to check whether the entry was actually there, because the sentence alone gave him no reason to trust it. A `grep` returning `1` is a fact that would come back `0` if the write had failed; the sentence would look identical either way.
  >
  > **Do not print the confirmation because it is required.** Print it because you ran the check and it passed. If you did not run the check, do not claim the entry is registered.

- **In the final status summary of your reply, include the queue registration as a verified item**, alongside the other completion evidence — e.g. `交接語已登載 pending.md（grep 命中 1）｜索引 33 則（--audit 通過）`. The user reads that summary to decide whether the handoff is finished; a handoff whose message never reached the queue is not finished, and that must be visible there rather than only in the tool output above.
- If the write fails (missing path that cannot be created, permission error), **say so explicitly** and tell the user to save the message manually — never fail silently

### Retirement check (after appending, same turn)

**Only check existing entries for the same workspace.** Do not scan the whole file or do a general tidy-up.

1. After appending, `grep` the pending file for other entries whose `| 工作區 |` matches this one
2. For each, ask one question: **does this handoff supersede it?** (later progress on the same work line → yes; same workspace but a different task → no)
3. For those superseded, cut the whole entry to `<PENDING_DIR>/archive/YYYY-MM.md` (same directory as `PENDING_FILE`; create the month file if absent) and prefix it with `## 離開原因：superseded — <one line>`
4. If unsure, **leave it alone** and ask the user in one line: "The pending file still has an entry <title> — does this handoff supersede it?"

**Retire only what this handoff supersedes.** Other stale entries (things the user finished themselves, external events that vanished) are out of scope — that remains a dedicated session's job.

> **Why this was added** (2026-08-29): this section previously said "do not judge whether older entries have gone stale," and the result was a file with an intake but no outlet — `archive/` was **completely empty** since its creation on 8/27, with all 13 entries piled in the pending file, 4 of them long superseded yet still marked "待啟動". The user's words: "there doesn't seem to be any automatic update mechanism when writing a handoff… if work stops halfway before a formal handoff, the pending file doesn't update itself, which gets awkward."
>
> The moment of writing is the **only** time it is knowable which entry this one supersedes — the superseded entry's context is still in the conversation. Miss it and only an after-the-fact sweep can recover it. The old rule deferred that judgment to "a dedicated session," and that session did not happen for two days.

**Still do not**:

- Deduplicate or re-sort the pending file as a whole
- Delete any entry (retiring means **cutting to** `archive/`, not deleting)
- Judge staleness of entries this handoff does not supersede
- Mirror the message anywhere else (`_monitoring/_handoffs/INDEX.md` indexes handoff **documents**, not messages)

## Step 5.6: Rebuild the pending-file index (mandatory, immediately after Step 5.5)

Once the append and the retirement check are both done, rebuild the index **in the same turn**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/pending_index.py"
```

The tool scans every entry in the pending file and rewrites a clickable index between the `<!-- INDEX:BEGIN -->` / `<!-- INDEX:END -->` markers at the top of the file (Obsidian wikilinks — clicking a title jumps straight to that entry), split into "待啟動" and "前置條件未成熟" groups, with deadlines surfaced.

**Rules**:

- **Order matters** — run it only after both the append and the retirement cut, or the index will miss the new entry or retain a retired one
- The tool is **idempotent**: re-running replaces only the index block, never appends or touches anything else. Safe to re-run at any point
- The index block is tool-maintained. **Neither humans nor AI may hand-edit it** — manual changes are overwritten on the next run
- Paste the tool's output line (e.g. `索引已更新：...（33 則）`) into your reply as completion evidence (per the completion gate in Step 4)
- **Then run `--audit` and paste that output too.** `--check` only confirms the index matches a freshly computed one — the tool compared against itself, which cannot reveal that the generator is wrong. `--audit` asserts the output is *correct*: every entry indexed, none duplicated within a section, no back-link inside a handoff message's fence. Its `N 則被索引` figure is also the second half of the Step 5.5 proof — it says the new entry is not merely present in the file but actually reached the index the user navigates by.

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/pending_index.py" --audit
  ```
- **Reconcile the entry count against what you actually did — not against "+1".** Step 5.5 can both append and retire in the same turn, so compute the expected count as `before + appended − retired`. Appending one while retiring one nets **zero change**, and that is correct, not a fault. Only stop and investigate when the count disagrees with that arithmetic.
  > Established 2026-09-04, from a live acceptance test: an append-plus-retirement turn left the count at 33→33 with a perfectly correct index (0 broken links, 0 missing). A naive "+1" expectation flags that healthy case as a failure — and, worse, would mask the real fault it was meant to catch.
  - The tool identifies an entry by its `### 交接語` block, not by the title format, so a title that deviates is still counted; a section with no `### 交接語` block is silently skipped. If the count is short, look for a missing or misspelled `### 交接語` heading first
- If the tool is missing or fails, **say so explicitly** and warn that the index is stale — never fail silently

> **Why a tool rather than having the model write the index** (established 2026-09-03): the index must correspond entry-by-entry, and hand-writing it at 31 entries reliably introduces errors while burning tokens on every handoff. A tool can be verified with `--check`; a hand-written index cannot be verified at all.
>
> Building it immediately surfaced an edge case a model would gloss over: `[2026-06 → 提列 2026-08-31]` carries only year-month, so a hardcoded `YYYY-MM-DD` regex silently skipped it — 31 entries indexed as 30. That is precisely the value of verifying with `grep` instead of eyeballing.

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
