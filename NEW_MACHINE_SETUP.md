# grp-kb-mcp — New Machine Setup

A step-by-step guide for setting up **grp-kb-mcp** (semantic search over an
Acumatica KB Obsidian vault) on a fresh computer — including how to build the
knowledge base itself if one doesn't already exist.

Published on PyPI as [`grp-kb-mcp`](https://pypi.org/project/grp-kb-mcp/) (the
Python package name stays `kb_mcp`). **Read this first — it's a different kind
of setup than a typical PyPI tool:** installing the package gets you the *server
code* only. It does nothing useful without a real, embedded Obsidian vault behind
it — Part A covers getting one, either by receiving access to an existing one or
building one from scratch.

---

## The three layers, and why each exists

| Layer | What it is | Who/what provides it |
|---|---|---|
| 1. The notes | Plain markdown files (your KB content) | You write them, or someone shares an existing vault |
| 2. The embeddings | A vector per note, computed by the **Smart Connections** Obsidian plugin | Obsidian + Smart Connections, one-time per note |
| 3. The search server | `grp-kb-mcp` — reads the precomputed vectors, embeds your *query* the same way, ranks by similarity | This package |

The reason this is a 3-layer setup instead of a single install: grp-kb-mcp never
talks to Obsidian directly, and it never computes note embeddings itself — it
only *reads* what Smart Connections already computed. That's also why the
**embedding model must match exactly** between layers 2 and 3 (more on this in
Part A) — mismatched models produce vectors that aren't comparable, and the
mismatch fails silently (see the warning box below), not with a clear error.

---

## Part A — Get or build the knowledge base

### Path 1 — Someone already maintains a vault (fastest)

Ask them to share the vault folder with you (e.g. a OneDrive "Add shortcut"
share, or any file-sync method). Note the **full local path** where it lands on
your machine — you'll need it in Part D. Skip to **Part B**.

Practical expectations for a vault of real size: order of magnitude ~800 MB,
~12,000 embedding files — the first sync may take a while depending on your
connection.

> **⚠️ On this path, do NOT install Obsidian or Smart Connections.**
>
> They are the *authoring* layer (layer 2). You are only *reading* — the shared
> vault already contains its embeddings, in the `.smart-env` folder inside it,
> and grp-kb-mcp reads those directly. Nothing here needs Obsidian.
>
> This is not a "you can skip it" nicety — installing them is the single most
> common way this setup goes wrong. **Smart Connections does not wait for your
> file sync to finish.** Enable it while OneDrive is still pulling ~12,000
> `.ajson` files and it sees a partial/empty `.smart-env`, concludes the notes
> are unembedded, and re-embeds all ~12,000 of them. It wins the race; the real
> vectors landing afterwards are ignored. Hours of CPU to recompute what you had
> already been given.
>
> Only install Obsidian + Smart Connections if this machine will **author or
> edit notes**. If it does, its bundled model MUST match the one that produced
> the existing vectors — see the A2.5 warning.

**Let the sync FULLY complete before running anything.** Two steps:

1. **Defeat Files On-Demand.** It is ON by default on a fresh Windows machine,
   which leaves files as cloud-only placeholders — `build_index` then reads no
   vectors and produces a silently empty index. Right-click the synced vault
   folder → **"Always keep on this device"**.
2. **Verify zero placeholders** before continuing (PowerShell; `0x400000` is
   `RecallOnDataAccess`, the dehydrated-placeholder attribute):

   ```powershell
   $v = "C:\path\to\Acumatica-KB"
   $f = Get-ChildItem $v -Recurse -File -Force
   "files: {0}  MB: {1}  cloud-only: {2}" -f $f.Count,
     [math]::Round(($f | Measure-Object Length -Sum).Sum/1MB,1),
     ($f | Where-Object { $_.Attributes -band 0x400000 }).Count
   ```

   `cloud-only` must be **0**. A healthy reference (2026-07-15): 11,941 `.md`
   + 12,358 `.smart-env` files, ~740 MB, 0 cloud-only.

**Shortcut — skip the index build entirely.** `build_index`'s output is just two
files. If the vault owner sends you their `kb_index.npy` + `kb_meta.json`
(~206 MB), drop them in a folder, point `KB_MCP_INDEX_DIR` at it, and skip
Part D. They are gitignored (so a `git clone` never brings them), which is the
*only* reason Part D exists on this path.

### Path 2 — Building the knowledge base from scratch

**A2.1 — Install Obsidian.**
Download from [obsidian.md](https://obsidian.md/) (official site) and install
for your OS.

**A2.2 — Create a vault.**
On first launch, choose "Create new vault" and pick a folder — this folder
*is* the vault; every markdown file you put inside it becomes searchable.

**A2.3 — Add your KB content.**
Populate the vault folder with markdown (`.md`) files — your product docs,
process notes, reference material, whatever the knowledge base should cover.
This part is entirely content-specific; there's no fixed procedure beyond "put
markdown files in the vault folder" (Obsidian will pick up files added outside
the app too, e.g. copied in via File Explorer).

**A2.4 — Install the Smart Connections plugin.**
In Obsidian: **Settings → Community plugins**. If prompted, turn off
**Restricted mode**. Click **Browse**, search for **"Smart Connections"**,
click **Install**, then **Enable** it.

**A2.5 — Let it index — and don't change the embedding model.**
As soon as you enable it, Smart Connections starts computing an embedding for
every note automatically, using its **bundled local model**
(`TaylorAI/bge-micro-v2`) — this is the **default**, requires **no API key**,
makes **no external calls**, and needs no configuration. Just leave it running.

> **⚠️ Do not change the embedding model in Smart Connections' settings** (e.g.
> to an Ollama or OpenAI-backed one) unless you know what you're doing. grp-kb-mcp
> only reads vectors stored under the exact key `TaylorAI/bge-micro-v2` — if
> Smart Connections is set to a different model, its `.smart-env` files will
> have vectors under a *different* key, and `build_index` (Part D) will **skip
> every single note without any error message** — you'll get a technically
> successful index build containing zero real content. If you're not sure
> what's configured, leave the default alone.

**A2.6 — Wait for indexing to finish.**
Depends on vault size — for thousands of notes, expect real time, not
seconds. You can check progress via Obsidian's status bar / the Smart
Connections view. When it's done, the vault has a hidden `.smart-env/multi/`
folder full of `.ajson` files — that's the embedding data `build_index` (Part D)
reads.

---

## What else you need before continuing

| # | What | Who provides it |
|---|------|------------------|
| 1 | A computer with internet access | — |
| 2 | Claude Code CLI or Claude Desktop installed | You |
| 3 | The vault from Part A | You (via either path above) |
| 4 | `uv` installed | You |

There is **no Acumatica login or API credential needed for this tool** (that's
grp-mcp, a separate setup) — the only "credential" here is the vault itself.

---

## Part B — Install `uv`

**Windows (PowerShell):**
```powershell
winget install --id=astral-sh.uv -e
```
**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Verify: `uv --version`

**Note:** grp-kb-mcp needs **Python 3.11+** (grp-mcp, if you've also set that up,
only needs 3.10+ — different requirement, don't assume they're the same). `uv`
can provision the right Python version itself; you don't need to separately
install Python.

---

## Part C — Install Claude Code CLI (if not already installed)

Follow Anthropic's official Claude Code installation instructions
([docs.claude.com](https://docs.claude.com)), then confirm: `claude --version`

---

## Part D — Build the search index (one-time, or whenever the vault is refreshed)

Unlike grp-mcp, this step needs a real Python environment (not just `uvx`
running a single command) because it runs a module, not a console script.

**Recommended — install into a venv** (simplest, most reliable):
```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install grp-kb-mcp
```

Then build the index, pointing at wherever your vault lives (Part A's shared
folder, or the vault you just built) and a stable folder to store the built
index files:

**Windows (PowerShell):**
```powershell
$env:KB_VAULT_DIR = "C:\path\to\Acumatica-KB"
$env:KB_MCP_INDEX_DIR = "C:\path\to\a\folder\you\control"
python -m kb_mcp.build_index
```
**macOS/Linux:**
```bash
export KB_VAULT_DIR=/path/to/Acumatica-KB
export KB_MCP_INDEX_DIR=/path/to/a/folder/you/control
python -m kb_mcp.build_index
```

This reads the vault's precomputed `.smart-env` embeddings and writes two files
into `KB_MCP_INDEX_DIR`: `kb_index.npy` and `kb_meta.json`. **Note this exact
folder path** — the server needs the same `KB_MCP_INDEX_DIR` in Part F so it can
find them. This step does **not** need the search model or internet access
beyond what pip already used to install — it just repackages data Smart
Connections already computed.

**Check the output.** It prints how many vectors it found. If that number is
**0** despite the vault clearly having notes, the embedding-model mismatch
warned about in A2.5 is almost certainly why — check what model Smart
Connections actually used.

**Alternative — no persistent install**, using `uv run` (verified working, but
downloads a large dependency set — `numpy`/`scipy`/`torch`/`transformers` — each
time unless `uv`'s cache already has it):
```powershell
$env:KB_VAULT_DIR = "C:\path\to\Acumatica-KB"; $env:KB_MCP_INDEX_DIR = "C:\path\to\index\folder"
uv run --with grp-kb-mcp python -m kb_mcp.build_index
```

**Re-run this step whenever the vault is re-indexed** (new/changed notes need
their embeddings picked up again — in Obsidian, Smart Connections re-embeds
changed notes automatically as you edit; you only need to re-run `build_index`
to pull the *updated* vectors into grp-kb-mcp's own index files).

---

## Part E — (Optional) multiple vaults in one index

If you also have access to extra Smart Connections vaults you want searchable
alongside the primary one (e.g. a separate user-manuals vault), set
`KB_EXTRA_VAULTS` before running `build_index` (PowerShell:
`$env:KB_EXTRA_VAULTS = "GRP=C:\path\to\GRPUserManuals-Markdown"`; macOS/Linux:
`export KB_EXTRA_VAULTS=GRP=/path/to/GRPUserManuals-Markdown`). A `;`-separated
list of `LABEL=PATH` pairs. Each extra vault's results get tagged `guide=LABEL`,
filterable later via `search_kb(..., guide_filter="GRP")`. Skip this if you only
have the one vault.

---

## Part F — Register with Claude

### Claude Code (CLI)

Using the venv install from Part D:
```powershell
claude mcp add grp-kb-mcp -s user -e KB_VAULT_DIR="C:\path\to\Acumatica-KB" -e KB_MCP_INDEX_DIR="C:\path\to\a\folder\you\control" -- "C:\path\to\.venv\Scripts\grp-kb-mcp.exe"
```

Using `uvx` instead (server run only — this part is a plain console script, so
`uvx` works the same simple way it does for grp-mcp):
```powershell
claude mcp add grp-kb-mcp -s user -e KB_VAULT_DIR="C:\path\to\Acumatica-KB" -e KB_MCP_INDEX_DIR="C:\path\to\a\folder\you\control" -- uvx grp-kb-mcp
```

`KB_MCP_INDEX_DIR` **must match exactly** what you used in Part D, or the server
won't find the index it built and will refuse to start.

### Claude Desktop

```json
{
  "mcpServers": {
    "grp-kb-mcp": {
      "command": "uvx",
      "args": ["grp-kb-mcp"],
      "env": {
        "KB_VAULT_DIR": "C:\\path\\to\\Acumatica-KB",
        "KB_MCP_INDEX_DIR": "C:\\path\\to\\a\\folder\\you\\control"
      }
    }
  }
}
```

---

## Part G — Restart and verify

1. **Restart Claude Code / Claude Desktop completely.**
2. Ask Claude to run `search_kb` with any query (e.g. "chart of accounts"). A
   working setup returns a JSON array of results with `score`/`path`/`snippet`.
3. **First search downloads the query-embedding model** (`TaylorAI/bge-micro-v2`,
   ~45 MB) automatically from Hugging Face — needs internet access on that
   first call, cached locally after. This is the **same model** Smart
   Connections used in Part A2.5 — that's what makes the query vector and the
   note vectors comparable.

If it fails on startup with "Index not found," `KB_MCP_INDEX_DIR` doesn't match
between Parts D and F. If it exits with "Set KB_VAULT_DIR env var," the vault
path in Part F is wrong or the folder hasn't finished syncing yet. If
`search_kb` returns results but they're all irrelevant nonsense, re-check the
"0 vectors found" warning in Part D — the embedding-model mismatch produces
exactly this kind of silent, confusing failure.

---

## Troubleshooting — "why is my new laptop re-embedding / downloading again?"

The vault and its embeddings live in OneDrive and sync. So on a fresh machine
these three things have three *different* causes — only one is a bug.

| Symptom | Cause | Fix |
|---|---|---|
| Smart Connections re-embeds all ~12,000 notes | **Bug.** Obsidian + SC were installed on a read-only machine, and SC started before the sync finished (or read placeholders) | Don't install Obsidian/SC on this path at all (Part A, Path 1). If already installed: let the sync fully complete FIRST, then reopen |
| `build_index` must be re-run | **Expected.** `kb_index.npy` / `kb_meta.json` are gitignored, so a `git clone` never carries them | Run Part D — it's offline and needs no model. Or copy the 2 files (~206 MB) from a machine that has them |
| ~68 MB model downloads on first search | **Expected by design.** The model lives in the HuggingFace cache (`HF_HOME`), not in the vault — it embeds your *query* at search time | Let it download once. Or copy the `HF_HOME` folder over and set `HF_HOME` to it |

Key point: **synced vault ≠ no re-embed.** Being fully synced is exactly why a
re-embed is a red flag — the vectors were already there. The race is against
sync completion, not against OneDrive having the data.

Diagnosing an empty/garbage index (`build_index` reports 0 vectors, or search
returns nothing):

1. **Placeholders** — run the `cloud-only` check in Part A, Path 1. Must be `0`.
2. **Model mismatch** — the A2.5 warning. If SC used a model other than
   `TaylorAI/bge-micro-v2`, its vectors sit under a different key and
   `build_index` skips those notes **silently**, reporting a clean build with no
   content. This fails quietly, which is what makes it nasty.
3. **Stale index** — the index is a snapshot; re-run Part D after any vault
   refresh.

---

## Notes / gotchas

- **This tool is a snapshot, not live.** Search results reflect the vault's
  embeddings as of whenever `build_index` last ran — new/edited notes won't
  show up in search until you re-run Part D (even though Smart Connections
  itself re-embeds them automatically inside Obsidian).
- **The embedding model must match end-to-end**: Smart Connections (Part A2.5)
  and grp-kb-mcp's own query embedding (Part G) both need to be
  `TaylorAI/bge-micro-v2` — it's the default on both sides, so as long as you
  don't deliberately change either, this takes care of itself.
- **Much heavier install than grp-mcp** — `sentence-transformers` pulls in
  `torch`, expect real download time and disk usage on first setup, not
  seconds.
- **Python 3.11+ required** — check with `python --version` before Part D if
  installing manually rather than letting `uv` provision it.
- **No bundled config UI** for this tool (unlike grp-mcp's `grp-mcp-ui`) —
  everything is environment variables, set as shown above.
