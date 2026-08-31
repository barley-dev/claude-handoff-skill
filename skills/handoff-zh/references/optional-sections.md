# Optional Sections

Not every handoff needs every section. Use the decision rules below to pick which optional blocks to include.

## Core sections (always present)

Already defined in `SKILL.md` main flow. This file covers only the *optional* blocks that append after the core.

## Optional section decision table

| Section | Include when | Skip when |
|---------|--------------|-----------|
| Key files quick reference | Workspace has 3+ important reference files | Fewer than 3 relevant files |
| Cross-workspace links | Conversation touched multiple workspaces | Single workspace |
| Schedule / timeline | Tasks have dates or deadlines | No date-sensitive work |
| Recommended execution order | Tasks have dependencies | Tasks are independent |
| Historical context | Previous handoff transcript exists and contains info not in current decisions | No prior handoffs |
| Prior handoff index | This is the 2nd+ handoff in a continuing series | First handoff on this topic |
| Verification anchors | Conversation produced decisions (methodology, architecture, policy) that later Wiki compilation might compress | Pure execution work with no long-term claims |
| Next-step tool recommendation | Next session benefits from a specific tool/model choice | Default tool is obvious |

## Templates

### Key files quick reference

```markdown
## Key files

| Purpose | Path |
|---------|------|
| Workspace index | `~/...INDEX.md` |
| Design doc | `~/...` |
```

### Cross-workspace links

```markdown
## Related workspaces

| Workspace | Relation |
|-----------|----------|
| `~/...` | ... |
```

### Schedule / timeline

```markdown
## Schedule overview

(table or list with dates, items, status)
```

### Recommended execution order

```markdown
## Recommended execution order

1. Do X first (Y depends on its output)
2. Then Y
3. Finally Z
```

### Historical context

When a transcript of prior discussion is available (e.g., at a path declared in the user's CLAUDE.md), check whether it contains context not already covered in "Key decisions." If yes, merge the relevant excerpts into "Key decisions." Do not create a separate file.

### Prior handoff index

```markdown
## Previous handoffs

- Previous: `~/...Handoff_YYYY-MM-DD_xxx.md`
```

### Verification anchors

```markdown
## Verification anchors

<!-- Uncompressed original decisions, for future sessions to check against Wiki/memory for drift -->

| Decision | Original wording (verbatim) | Context | Date |
|----------|----------------------------|---------|------|
| ... | ... | ... | YYYY-MM-DD |
```

Use this when the conversation produced a decision that is likely to be summarized later and might lose nuance. The verbatim wording lets future sessions verify that any compressed version is faithful.

### Next-step tool recommendation

Use this when the next session benefits from a specific tool or model choice, or when tasks can be parallelized. Skip if the default tool is obvious.

When deciding the recommendation, consider these four dimensions:

1. **Execution environment.** Which tool is best suited to the task? Factors include whether the task needs filesystem access, cross-workspace MCP tools, long-context processing, or specialized capabilities (search, code execution, vision).
2. **Parallelism.** If the pending work contains multiple independent tasks, identify which can run in parallel and which have sequential dependencies.
3. **Sub-agent model selection.** If the task involves parallel sub-agents, pick model per task type:
   - Extraction / summarization / simple transformation → lighter model (cost-efficient, sub-agent)
   - Merging, cross-referencing, reasoning → more capable model (main agent)
   - Trivial format-only transformation → smallest model
4. **Cross-tool collaboration.** If the task needs multiple tools working together, explicitly list which tool owns which piece and how outputs flow between them.

Template:

```markdown
## Next-step tool and division of labor

| Task | Recommended tool | Model | Parallelizable? | Notes |
|------|------------------|-------|-----------------|-------|
| Task A | [tool name] | [model tier] | Yes / No | ... |
| Task B | [tool name] | [model tier] | Yes / No | ... |
```

For simple cases (single task, obvious tool), one line in the handoff message suffices instead of a full table:

```
Recommended tool: [tool name with model, or "human review needed"]
```

## Cross-workspace cross-index

When the conversation is anchored in workspace A but produces results relevant to workspace B:

1. The **main handoff** lives in workspace A's `HANDOFF_DIR`
2. A **one-line cross-index** lives in workspace B's `HANDOFF_DIR`, pointing to the main handoff:

```markdown
> Cross-index: the related handoff for this workspace is at
> `<WORKSPACE_A>/_handoffs/Handoff_YYYY-MM-DD_xxx.md`
```

This ensures that whichever workspace the next session starts in, it can find the relevant handoff without having to search across workspaces.
