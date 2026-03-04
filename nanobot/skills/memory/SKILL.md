---
name: memory
description: Enhanced memory system with two layers - grep-based MEMORY.md/HISTORY.md (always available) plus optional OpenViking semantic search for structured conversation storage and advanced recall. Use when users ask to remember information, search past conversations, recall previous discussions, or work with documents. Triggers on "remember this", "what did we discuss", "search my history", "recall", "find in memory", or any memory-related query. Always use embedded mode for OpenViking (no separate service needed).
always: true
---

# Memory System

A dual-approach memory system combining simple markdown files with optional semantic search via OpenViking.

## Core Layer (Always Available)

The foundational memory system that works without any dependencies:

### Structure

- `memory/MEMORY.md` — Long-term facts (preferences, project context, relationships). Always loaded into your context.
- `memory/HISTORY.md` — Append-only event log. NOT loaded into context. Search it with grep. Each entry starts with `[YYYY-MM-DD HH:MM]`.

### Search Past Events

```bash
grep -i "keyword" memory/HISTORY.md
```

Use the `exec` tool to run grep. Combine patterns: `grep -iE "meeting|deadline" memory/HISTORY.md`

### When to Update MEMORY.md

Write important facts immediately using `edit_file` or `write_file`:
- User preferences ("I prefer dark mode")
- Project context ("The API uses OAuth2")
- Relationships ("Alice is the project lead")

### Auto-consolidation

Old conversations are automatically summarized and appended to HISTORY.md when the session grows large. Long-term facts are extracted to MEMORY.md. You don't need to manage this.

---

## Enhanced Layer (OpenViking) — Optional

OpenViking provides semantic search, structured conversation storage, and tiered content access. It runs in **embedded mode** — no separate service needed, everything happens in-process.

**When to use OpenViking:**
- User explicitly requests semantic search or advanced recall
- Conversation contains important technical details worth structured storage
- User provides documents/files that need persistent context
- Session is lengthy (10+ turns) and would benefit from structured memory
- User asks "what did we discuss about X?" where grep might miss semantic connections

**When NOT to use OpenViking:**
- Simple fact storage (use MEMORY.md directly — it's faster)
- Quick grep searches (grep is sufficient for keyword lookup)
- User hasn't provided enough context to warrant structured storage

### Setup Check

Before using OpenViking commands, verify the CLI script is available:

```bash
ls scripts/openviking_client.py 2>/dev/null
```

If missing, OpenViking enhancement is not installed. Fall back to core layer (grep-based search).

---

## OpenViking: Conversation Storage

### Session Lifecycle

**1. Session Start (Beginning of Conversation)**

When starting a new conversation or when you decide to use structured storage:

```bash
# Sessions are created implicitly when you commit
# No upfront "create session" step needed
```

**2. Tracking Conversations**

Build up conversation turns in memory during the session. You'll commit them as a batch when appropriate.

**3. Session Commit (When to Store)**

Commit conversations to OpenViking when:
- Conversation reaches 8-10 turns
- User shares important information (preferences, decisions, technical details)
- User explicitly says "remember this" or similar
- Topic shifts significantly
- Session ending signals ("thanks", "goodbye")

**How to commit:**

Create a temporary JSON spec file with the conversation turns:

```bash
cat > /tmp/session_spec.json << 'EOF'
{
  "messages": [
    {"role": "user", "parts": ["First user message here"]},
    {"role": "assistant", "parts": ["Your response here"]},
    {"role": "user", "parts": ["Second user message"]},
    {"role": "assistant", "parts": ["Your second response"]}
  ],
  "used": []
}
EOF

python scripts/openviking_client.py --data-dir ~/.nanobot/openviking session /tmp/session_spec.json
```

The `used` array can include viking:// URIs of resources you referenced during conversation.

**Output:** On commit, OpenViking extracts structured memories to:
- `viking://user/memories/` — User preferences and context
- `viking://agent/memories/` — Agent-learned patterns

---

## OpenViking: File Ingestion

When the user provides files, documents, or directories:

```bash
# Ingest a file
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking add-resource /path/to/file.pdf --wait

# Ingest a directory
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking add-resource /path/to/docs/ --wait

# Returns: {"root_uri": "viking://resources/docs"}
```

The `--wait` flag blocks until semantic indexing completes. Always use it so the content is immediately searchable.

---

## OpenViking: Memory Recall

Use a **tiered approach** to minimize token usage:

### Tier 1: Search (Find Relevant URIs)

Start with semantic search to locate relevant content:

```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking find "authentication flow" "viking://resources/"
```

Returns JSON array: `[{"uri": "viking://resources/docs/auth.md", "score": 0.92, ...}, ...]`

Search within user memories:
```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking find "Python preferences" "viking://user/memories/"
```

### Tier 2: Triage (Filter with Abstract)

For each search result, get a ~100 token summary to decide relevance:

```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking abstract "viking://resources/docs/auth.md"
```

This is fast and cheap. Use it to filter out non-relevant matches before reading full content.

### Tier 3: Structure (Overview for Directories)

If the URI is a directory and you need to understand its structure:

```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking overview "viking://resources/docs/"
```

Returns a ~2000 token overview. Only works on directories.

### Tier 4: Full Content (Read)

When you've confirmed relevance, read the full content:

```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking read "viking://resources/docs/auth.md"
```

Returns complete file contents. Use sparingly — only after abstract confirms relevance.

**Workflow example:**
1. Search: find 5 URIs related to query
2. Abstract: check all 5, identify 2 relevant ones
3. Read: fetch full content only for those 2

---

## OpenViking: Exploration Commands

### List Directory Contents

```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking ls "viking://resources/"
```

### Recursive Tree

```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking tree "viking://resources/docs/"
```

### Pattern Matching

```bash
python scripts/openviking_client.py --data-dir ~/.nanobot/openviking glob "**/*.md" "viking://resources/"
```

---

## Choosing the Right Approach

| Task | Use This |
|------|----------|
| Store simple fact | Edit MEMORY.md directly |
| Search for keyword | grep on HISTORY.md |
| Store structured conversation | OpenViking session commit |
| Ingest user's documents | OpenViking add-resource |
| Semantic search ("concepts related to X") | OpenViking find → abstract → read |
| Keyword search ("find 'deadline'") | grep HISTORY.md |

---

## URI Namespaces (OpenViking)

| Namespace | Contents |
|-----------|----------|
| `viking://resources/` | Ingested documents and data |
| `viking://user/memories/` | User preferences and context (auto-extracted from sessions) |
| `viking://agent/memories/` | Agent-learned patterns (auto-extracted from sessions) |

---

## Important Notes

**Embedded Mode**: All OpenViking commands run in embedded mode. Each command invocation:
1. Starts AGFS subprocess via `client.initialize()`
2. Executes the operation
3. Shuts down AGFS via `client.close()`

You never need to start a separate OpenViking service. It's all self-contained.

**Data Directory**: OpenViking data is stored in `~/.nanobot/openviking/` by default (via `--data-dir` flag). This is separate from the core memory files in `~/.nanobot/workspace/memory/`.

**Fallback**: If OpenViking is unavailable or fails, always fall back to the core layer (MEMORY.md + HISTORY.md + grep). The core layer is the foundation.

---

## Example: Complete Memory Workflow

**User says:** "Remember that I prefer TypeScript and hate using 'any' types. Also, here's our API documentation (provides api.pdf)."

**Your actions:**

1. **Store preference in MEMORY.md** (fast, always loaded):
   ```
   Edit MEMORY.md, add:
   ## Coding Preferences
   - Prefers TypeScript over JavaScript
   - Avoids 'any' types, prefers explicit typing
   ```

2. **Ingest the document**:
   ```bash
   python scripts/openviking_client.py --data-dir ~/.nanobot/openviking add-resource api.pdf --wait
   ```

3. **Track this conversation turn** (in memory, for eventual session commit).

4. **When session ends or reaches 10 turns, commit**:
   ```bash
   cat > /tmp/session_spec.json << 'EOF'
   {
     "messages": [
       {"role": "user", "parts": ["Remember that I prefer TypeScript..."]},
       {"role": "assistant", "parts": ["I've stored your preference..."]}
     ],
     "used": ["viking://resources/api.pdf"]
   }
   EOF

   python scripts/openviking_client.py --data-dir ~/.nanobot/openviking session /tmp/session_spec.json
   ```

Later, when user asks: "What did we discuss about TypeScript?"

1. **Quick grep check**:
   ```bash
   grep -i "typescript" memory/HISTORY.md
   ```

2. **Semantic search for deeper context**:
   ```bash
   python scripts/openviking_client.py --data-dir ~/.nanobot/openviking find "TypeScript preferences" "viking://user/memories/"
   ```

3. **Read relevant results**:
   ```bash
   python scripts/openviking_client.py --data-dir ~/.nanobot/openviking abstract "viking://user/memories/session-XYZ"
   python scripts/openviking_client.py --data-dir ~/.nanobot/openviking read "viking://user/memories/session-XYZ"
   ```

---

## Reference

- Core layer: `memory/MEMORY.md` (facts), `memory/HISTORY.md` (events)
- OpenViking CLI: `scripts/openviking_client.py --help`
- OpenViking data: `~/.nanobot/openviking/`
- URI scheme: `viking://resources/`, `viking://user/memories/`, `viking://agent/memories/`
