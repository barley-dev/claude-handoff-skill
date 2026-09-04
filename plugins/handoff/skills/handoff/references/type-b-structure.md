# Type B: Code Task Handoff

**Load this reference when the handoff is for a task that an automated agent (Claude Code or similar) will execute.** Regular conversational handoffs (planning, design, writing) use the default Type A structure in `SKILL.md` and do not need this file.

## When this applies

The handoff is Type B when the conversation produces an actionable task that another agent will pick up and execute. Indicators:

- Code implementation or modification
- Script writing
- File transformation or batch operation
- Any task with programmatic acceptance criteria

The key distinction from Type A: the receiving agent needs **explicit task objectives**, **current state of the code**, and **verifiable acceptance criteria**, not just conversational context.

## Structure

Insert these sections between the core blocks and the optional sections:

```markdown
## Task objective

(One sentence: what needs to be accomplished)

## Current code and logic

(Current behavior of the relevant functions / modules, with full file paths)
(Include key code snippets inline)

## Issues to address

For each issue:
- Description
- Suggested approach

## Acceptance criteria

(Verifiable, concrete conditions)

1. `command --flag input` produces expected output
2. Behavior without `--flag` is unchanged (backwards compatible)
3. ...

## Out of scope

(Explicit exclusions — keeps the receiving agent from overreaching)
```

## Writing guidelines

- **Acceptance criteria must be executable.** "Works correctly" is not a criterion. "Command X produces output Y" is.
- **Current-state snippets are faster than links.** Paste the relevant 10–30 lines inline rather than asking the receiving agent to navigate a repo.
- **Out-of-scope is as important as scope.** Receiving agents tend to overreach; stating what *not* to touch prevents wasted work and unintended changes.
