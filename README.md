# kb-mcp

Semantic search MCP server for the Acumatica KB Obsidian vault.  
Reuses the embeddings already computed by the Smart Connections plugin (`TaylorAI/bge-micro-v2`, 384-dim).

## Tools

| Tool | What it does |
|------|-------------|
| `search_kb(query, top_k, source_only, guide_filter)` | Semantic search — embed query, cosine-search ~89k vectors, return top results with snippet |
| `read_kb_file(path)` | Read full content of a KB file by relative path |

## Setup

### 1. Install

```bash
cd C:\Users\CSM-Arvindh\OneDrive - Censof Holdings\Desktop\OPEX\kb-mcp
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### 2. Build the index (run once, ~2 min)

```bash
# with .venv active, from the kb-mcp folder:
set KB_VAULT_DIR=C:\Users\CSM-Arvindh\OneDrive - Censof Holdings\Desktop\OPEX\Acumatica-KB
python -m kb_mcp.build_index
```

This creates `kb_index.npy` and `kb_meta.json` inside `src\kb_mcp\`.  
Re-run only if you add new notes to the vault (and re-index in Obsidian Smart Connections first).

### 3. Register with Claude Desktop

Add to `claude_desktop_config.json` (found at `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "kb-mcp": {
      "command": "C:\\Users\\CSM-Arvindh\\OneDrive - Censof Holdings\\Desktop\\OPEX\\kb-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "kb_mcp.server"],
      "env": {
        "KB_VAULT_DIR": "C:\\Users\\CSM-Arvindh\\OneDrive - Censof Holdings\\Desktop\\OPEX\\Acumatica-KB"
      }
    }
  }
}
```

Restart Claude after adding.

### 4. First query (model download)

The `TaylorAI/bge-micro-v2` model (~45 MB) downloads automatically on the first `search_kb` call and is cached locally by HuggingFace.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_VAULT_DIR` | auto-detected | Path to the Acumatica-KB vault folder |
| `KB_MCP_INDEX_DIR` | `src/kb_mcp/` | Where `kb_index.npy` and `kb_meta.json` live |
| `KB_SNIPPET_LINES` | `30` | Lines to include in each result snippet |
