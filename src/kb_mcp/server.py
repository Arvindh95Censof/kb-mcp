"""
kb-mcp server  —  semantic search over the Acumatica KB for Claude.

Tools exposed:
  search_kb(query, top_k, source_only, guide_filter)
      Embed the query with TaylorAI/bge-micro-v2, cosine-search the index,
      return top_k results with snippet text, path, heading, score.

  read_kb_file(path)
      Read the full markdown content of a KB file by its relative path.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from mcp.server.fastmcp import FastMCP

# ── paths ──────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent

VAULT_DIR = Path(os.environ.get("KB_VAULT_DIR", ""))
if not VAULT_DIR or not VAULT_DIR.exists():
    candidate = _HERE.parent.parent.parent / "Acumatica-KB"
    if candidate.exists():
        VAULT_DIR = candidate
    else:
        sys.exit("Set KB_VAULT_DIR env var to the Acumatica-KB folder.")

INDEX_DIR = Path(os.environ.get("KB_MCP_INDEX_DIR", _HERE))
INDEX_NPY = INDEX_DIR / "kb_index.npy"
INDEX_META = INDEX_DIR / "kb_meta.json"

SNIPPET_LINES = int(os.environ.get("KB_SNIPPET_LINES", "30"))

# ── load index ─────────────────────────────────────────────────────────────────
if not INDEX_NPY.exists() or not INDEX_META.exists():
    sys.exit(
        f"Index not found at {INDEX_DIR}.\n"
        "Run:  python -m kb_mcp.build_index"
    )

print(f"Loading index from {INDEX_DIR} …", file=sys.stderr, flush=True)
_vectors = np.load(str(INDEX_NPY))          # (N, 384) float32, L2-normalised
_meta: list[dict] = json.loads(INDEX_META.read_text(encoding="utf-8"))
print(f"Index ready: {len(_meta)} vectors.", file=sys.stderr, flush=True)

# Extra vaults (e.g. GRP) bake an absolute 'vault_root' into their records, so
# the server can read their files without any extra env. Collect them for
# read_kb_file path resolution.
_extra_roots = sorted({m["vault_root"] for m in _meta if m.get("vault_root")})
if _extra_roots:
    print(f"Extra vault roots: {_extra_roots}", file=sys.stderr, flush=True)

# ── embed model ──────────────────────────────────────────────────────────────
# Loaded EAGERLY here, on the main thread, before mcp.run(). Do NOT make this
# lazy: importing sentence_transformers from any non-main thread inside this
# process (FastMCP's tool-dispatch thread, or a startup daemon thread) hangs
# indefinitely — the import never returns. The main-thread import works fine
# (~7-13s). This adds a one-time delay before the server starts answering the
# stdio handshake, but every query afterwards is instant.
print("Loading TaylorAI/bge-micro-v2 …", file=sys.stderr, flush=True)
from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("TaylorAI/bge-micro-v2")
print("Model ready.", file=sys.stderr, flush=True)


def _get_model():
    return _model


def _embed(text: str) -> np.ndarray:
    vec = _get_model().encode([text], normalize_embeddings=True)[0]
    return vec.astype(np.float32)


def _read_snippet(md_path: str, lines: Optional[list], vault_root: str = "") -> str:
    """Read lines from the vault file. Falls back to first SNIPPET_LINES lines."""
    root = Path(vault_root) if vault_root else VAULT_DIR
    full = root / md_path
    if not full.exists():
        return ""
    all_lines = full.read_text(encoding="utf-8").splitlines()
    if lines and len(lines) == 2:
        start = max(0, lines[0] - 1)
        end = min(len(all_lines), lines[1])
        return "\n".join(all_lines[start:end])
    return "\n".join(all_lines[:SNIPPET_LINES])


# ── MCP server ──────────────────────────────────────────────────────────────
mcp = FastMCP("kb-mcp")


@mcp.tool()
def search_kb(
    query: str,
    top_k: int = 10,
    source_only: bool = False,
    guide_filter: str = "",
) -> str:
    """
    Semantically search the Acumatica KB.

    Args:
        query:        Natural-language question or keywords.
        top_k:        Number of results to return (default 10, max 30).
        source_only:  If true, return one result per file (ignore sub-blocks).
        guide_filter: Optional filter — only return results where guide equals
                      this value (e.g. 'FormReference', 'GettingStarted',
                      'Implement', 'Dev_CustomizationUpdate').

    Returns:
        JSON array of results, each with:
          score, path, heading, title, breadcrumb, forms, guide, snippet
    """
    top_k = min(max(1, top_k), 30)
    qvec = _embed(query)                        # (384,)
    scores = _vectors @ qvec                    # (N,) cosine similarities

    # apply filters before ranking
    mask = np.ones(len(_meta), dtype=bool)
    if source_only:
        mask &= np.array([m["type"] == "source" for m in _meta])
    if guide_filter:
        gf = guide_filter.lower()
        mask &= np.array([m.get("guide", "").lower() == gf for m in _meta])

    filtered_scores = np.where(mask, scores, -2.0)
    top_idx = np.argpartition(filtered_scores, -top_k)[-top_k:]
    top_idx = top_idx[np.argsort(filtered_scores[top_idx])[::-1]]

    results = []
    for idx in top_idx:
        m = _meta[idx]
        snippet = _read_snippet(m["path"], m.get("lines"), m.get("vault_root", ""))
        results.append(
            {
                "score": round(float(scores[idx]), 4),
                "path": m["path"],
                "heading": m["heading"],
                "title": m["title"],
                "breadcrumb": m["breadcrumb"],
                "forms": m["forms"],
                "guide": m["guide"],
                "snippet": snippet,
            }
        )

    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp.tool()
def read_kb_file(path: str) -> str:
    """
    Read the full content of a KB file by its relative path (as returned by search_kb).

    Args:
        path: Relative path to the .md file, e.g.
              'AI_Assistant_Leveraging_the_AI_Assistant__e5b8f65c.md'
    """
    # primary vault first, then any extra vault roots (GRP, etc.)
    for root in [VAULT_DIR, *(Path(r) for r in _extra_roots)]:
        full = root / path
        if full.exists():
            return full.read_text(encoding="utf-8")
    return f"File not found: {path}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
