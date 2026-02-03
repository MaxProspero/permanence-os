# Memory System

Only four memory types exist:

1. **Canon Memory (Law):** `canon/*.yaml` (read-only to agents)
2. **Episodic Memory:** `memory/episodic/` (append-only task states)
3. **Working Memory:** `memory/working/` (scratch, cleared after tasks)
4. **Tool Memory:** `memory/tool/` (raw tool inputs/outputs; immutable)

Promotion path:

```
Working → Episodic → Canon (human ceremony only)
```

Tool memory can be ingested into `memory/working/sources.json` using `scripts/ingest_tool_outputs.py`.
