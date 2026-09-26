---
name: pending-review
description: Use when the user wants to review, sort, group, or prune their queue of pending handoffs rather than create a new one. Triggers include "整理待辦", "盤點", "整理 pending", "看一下待辦", "哪些可以退場", "重新分類", "review pending", "triage my queue", "what should I work on", or asking which queued items relate to each other.
---

# Pending Queue Review

This skill governs the *pending queue* — the central file of handoff messages awaiting pickup. It is the counterpart to the `handoff` skill:

| | `handoff` | `pending-review` (this skill) |
|---|---|---|
| Trigger | "I'm wrapping up" | "I want to tidy up" |
| Acts on | One new entry | The whole queue |
| Writes | Appends one entry | Regroups, retires, annotates |

They are deliberately separate because forcing a review through the handoff flow would mean triggering a handoff just to sort a list. They share no code — only the entry format, which lives in `<PENDING_DIR>/_format.md` (authoritative) or the template in the `handoff` skill.

## Step 0: Resolve paths and get the time

```bash
date "+%Y-%m-%d %H:%M %Z"
```

Resolve `PENDING_FILE` from the user's `CLAUDE.md` (see the `handoff` skill's `references/user-config.md`). If `<PENDING_DIR>/_format.md` exists, read it first — it defines the fields you are about to reason over.

## Step 1: Read the whole file before proposing anything

Read `PENDING_FILE` in full. Do not work from the index block — it is generated output and may lag the entries.

Count entries mechanically, never by eye:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/pending_index.py" --check
```

## Step 2: Build the dependency view from what is already written

**The relationships are already in the file** — they sit inside the `| 前置 |` and `| 連動 |` cells of individual entries, invisible because each is trapped in its own row. Extracting them requires no new input from the user.

For each entry, extract:

- `| 前置 |` — what it waits on. If the text names another entry (by title fragment, workspace path, or deliverable), that is an edge: **this entry is blocked by that one**
- `| 連動 |` — declared sibling relationships
- `| 期限 |` — a date, which orders everything
- `| 工作區 |` — shared workspace is weak evidence of relatedness

Then report, in this order:

1. **Deadline-bound**, sorted by date — these have externally imposed order
2. **Chains** — "finishing A unblocks B (and C)". State the unlock count; it is the strongest argument for what to do first
3. **Blocked** — each with `等：<what it waits on>`, so the user can see at a glance what is *not* actionable
4. **Independent singletons** — grouped by `| 下一步 |` (`AI` first: what can start without the user), topic as a secondary tag

> **Why this ordering**: the user's stated pain is "I can't see how they relate or what order to do them in" — not "there are too many". Hiding entries would make the screen cleaner while leaving that pain untouched. Surface structure instead of shortening the list.

## Step 3: Detect retirement candidates — propose, never move

Flag an entry as a retirement candidate when any of these holds:

| Signal | Proposed reason |
|---|---|
| Its deliverable verifiably exists | `completed` |
| A newer entry covers the same workspace and supersedes it | `superseded` |
| The user has said the work is off | `dropped` |
| Untouched for 60+ days, or self-labelled "low priority" / "after <month>" | ask — may be `dropped`, may just be slow |

The index already marks two of these mechanically — `已過` (deadline passed) and `久放` (no deadline, work dated 60+ days ago) — and counts them as "待確認去留" in its header line. Start from those labels, but verify each against the entry itself: the labels are computed from dates, not from whether the work moved. For `久放` entries with no deadline, `<PENDING_DIR>/someday.md` (if present) is a parking place that is not a retirement — propose it alongside the three reasons, and move only on approval.

**Before proposing `completed`, pass the completion gate**: run `ls` or `grep` to confirm the artifact exists, confirm it carries no pending markers ("待確認", "待審", "尚未查證", "TODO", "⬜"), and **paste the command and its output** into your report. A completion claim with no command output is a guess and must not be presented as fact. Filenames, directory names, file sizes and mtimes are clues about content, not content.

**Never cut an entry out on your own initiative.** Retirement is destructive to the user's queue: present the candidates with evidence and let them decide. On approval, move each whole entry to `<PENDING_DIR>/archive/YYYY-MM.md`, prefixed `## 離開原因：<completed|superseded|dropped> — <one line>`.

## Step 4: Rebuild the index (mandatory whenever entries or titles changed)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/pending_index.py"
python3 "${CLAUDE_PLUGIN_ROOT}/tools/pending_index.py" --check
```

Order matters: edit entries → retire → **then** rebuild. Rebuilding first leaves the index describing a file that no longer exists in that shape.

> This is not optional bookkeeping. The index's clickable titles are the user's daily path into the file (pick an entry → jump → copy the message → paste into a new session). On 2026-09-03 titles were edited without a rebuild and every link pointed at a title that no longer existed; the user reported "點了之後不會跳轉了". Paste the tool's output as evidence.

## Output discipline

- **One decision point per reply.** If several things need the user's ruling, rank them and ask only the most consequential; write the rest into the report rather than listing them in chat
- **No countdowns, no alarm symbols.** Deadlines are stated as dates. "3 days left" is computed at write time and is wrong tomorrow; a resident document is a clock the user consults, not an alarm that interrupts them
- Report the queue as a table, not prose
- Do not report line counts or file sizes — they go stale and nobody reads them
