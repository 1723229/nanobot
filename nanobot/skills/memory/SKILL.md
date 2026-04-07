---
name: memory
description: Two-layer memory system with Dream-managed knowledge files.
always: true
---

# Memory

## Structure

- `SOUL.md` — Bot personality and communication style. **Managed by Dream.** Do NOT edit.
- `USER.md` — User profile and preferences. **Managed by Dream.** Do NOT edit.
- `memory/MEMORY.md` — Long-term facts (project context, important events). **Managed by Dream.** Do NOT edit.
- `memory/history.jsonl` — append-only JSONL, not loaded into context. Prefer the built-in `grep` tool to search it.

## Search Past Events

`memory/history.jsonl` is JSONL format — each line is a JSON object with `cursor`, `timestamp`, `content`.

- For broad searches, start with `grep(..., path="memory", glob="*.jsonl", output_mode="count")` or the default `files_with_matches` mode before expanding to full content
- Use `output_mode="content"` plus `context_before` / `context_after` when you need the exact matching lines
- Use `fixed_strings=true` for literal timestamps or JSON fragments
- Use `head_limit` / `offset` to page through long histories
- Use `exec` only as a last-resort fallback when the built-in search cannot express what you need

Examples (replace `keyword`):
- `grep(pattern="keyword", path="memory/history.jsonl", case_insensitive=true)`
- `grep(pattern="2026-04-02 10:00", path="memory/history.jsonl", fixed_strings=true)`
- `grep(pattern="keyword", path="memory", glob="*.jsonl", output_mode="count", case_insensitive=true)`
- `grep(pattern="oauth|token", path="memory", glob="*.jsonl", output_mode="content", case_insensitive=true)`

## Important

- **Do NOT edit SOUL.md, USER.md, or MEMORY.md.** They are automatically managed by Dream.
- If you notice outdated information, it will be corrected when Dream runs next.
- Users can view Dream's activity with the `/dream-log` command.

## Semantic Memory

When semantic memory is enabled in config, use the native tools for concept-level recall, persistent document search, and structured memory operations.

### Available Tools

| Tool | Purpose |
|------|---------|
| `user_memory_search` | Semantic search over user memories |
| `openviking_search` | Semantic search across indexed resources |
| `openviking_read` | Read resource content at `abstract`, `overview`, or `read` level |
| `openviking_list` | List resources in a URI/path |
| `openviking_grep` | Regex search within indexed resources |
| `openviking_glob` | Glob pattern matching over indexed resources |
| `openviking_memory_commit` | Persist conversation messages into memory |
| `openviking_add_resource` | Ingest local files for semantic indexing |

### When To Use Semantic Memory

- User asks to remember information beyond the current session
- User asks what was discussed previously and keyword grep may be insufficient
- User provides documents/files that should remain searchable later
- You need semantic search over concepts instead of exact string matching

### When Not To Use Semantic Memory

- Exact keyword lookup in `memory/history.jsonl` is enough
- Small factual updates belong in Dream-managed memory files
- Semantic memory tools are unavailable or failing; fall back to grep-based retrieval

### Recommended Recall Flow

1. Search with `user_memory_search(...)` or `openviking_search(...)`
2. Triage matches with `openviking_read(..., level="abstract")`
3. Read full content only for relevant matches with `openviking_read(..., level="read")`

Examples:
- `user_memory_search(query="authentication flow")`
- `openviking_search(query="authentication flow", target_uri="viking://resources/")`
- `openviking_read(uri="viking://resources/docs/auth.md", level="abstract")`
- `openviking_read(uri="viking://resources/docs/auth.md", level="read")`

### Conversation Commit

Use `openviking_memory_commit` for important conversations when semantic memory is enabled.

- Commit when the user says "remember this"
- Commit when important preferences, decisions, or technical context appear
- Commit near the end of a substantial discussion if the content is likely to matter later

Example:
- `openviking_memory_commit(messages=[{"role": "user", "content": "I prefer TypeScript"}, {"role": "assistant", "content": "Noted"}])`

### File Ingestion

Use `openviking_add_resource` to ingest user-provided files so they become semantically searchable.

- `openviking_add_resource(local_path="/path/to/file.pdf", description="API documentation", wait=true)`

### URI Namespaces

| Namespace | Contents |
|-----------|----------|
| `viking://resources/` | Ingested documents and data |
| `viking://user/{user_id}/memories/` | User-specific memories |
| `viking://agent/{agent_space}/memories/` | Agent-learned memories |

### Fallback

- If semantic memory is unavailable, always fall back to the core layer: Dream-managed files plus `memory/history.jsonl` search.
