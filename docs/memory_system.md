# Memory System

Only four memory types exist:

1. **Canon Memory (Law):** `canon/*.yaml` (read-only to agents)
2. **Episodic Memory:** `memory/episodic/` (append-only task states + episodic_YYYY-MM-DD.jsonl)
3. **Working Memory:** `memory/working/` (scratch, cleared after tasks)
4. **Tool Memory:** `memory/tool/` (raw tool inputs/outputs; immutable)

Promotion path:

```
Working → Episodic → Canon (human ceremony only)
```

Tool memory can be ingested into `memory/working/sources.json` using `scripts/ingest_tool_outputs.py`.
Local documents can be ingested from `memory/working/documents` using `scripts/ingest_documents.py`.

To generate a Canon change draft from episodic memory (no Canon edits):

```bash
python scripts/promote_memory.py --count 5
python cli.py promote --count 5
```

The draft is written to `outputs/canon_change_proposal.md` by default.
You can override the draft output path with `PERMANENCE_PROMOTION_OUTPUT`.

Promotion queue (optional):

```bash
python cli.py queue list
python cli.py queue add --latest --reason "pattern repeat"
python cli.py queue clear
```

Use the promotion rubric at `docs/promotion_rubric.md` for Canon updates.
Override via `PERMANENCE_PROMOTION_RUBRIC` if needed.
