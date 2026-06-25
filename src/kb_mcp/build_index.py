"""
build_index.py  —  run this once to parse all .ajson embeddings and save a
numpy index + metadata JSON that the MCP server loads at startup.

Usage:
    python -m kb_mcp.build_index

Outputs (written next to this script's package, or to KB_MCP_INDEX_DIR env var):
    kb_index.npy      — float32 array of shape (N, 384)
    kb_meta.json      — list of N metadata dicts
"""

import json
import os
import sys
import numpy as np
from pathlib import Path

# ── locate the vault ──────────────────────────────────────────────────────────
VAULT_DIR = Path(os.environ.get("KB_VAULT_DIR", ""))
if not VAULT_DIR or not VAULT_DIR.exists():
    # try to find it relative to this file (kb-mcp is sibling of Acumatica-KB)
    here = Path(__file__).resolve().parent
    candidate = here.parent.parent.parent / "Acumatica-KB"
    if candidate.exists():
        VAULT_DIR = candidate
    else:
        sys.exit(
            "Cannot locate vault. Set KB_VAULT_DIR env var to the Acumatica-KB folder."
        )

SMART_ENV = VAULT_DIR / ".smart-env" / "multi"

INDEX_DIR = Path(os.environ.get("KB_MCP_INDEX_DIR", Path(__file__).resolve().parent))
INDEX_NPY = INDEX_DIR / "kb_index.npy"
INDEX_META = INDEX_DIR / "kb_meta.json"

MODEL_KEY = "TaylorAI/bge-micro-v2"
DIMS = 384


def parse_ajson(path: Path) -> dict:
    """Wrap the bare key:value pairs in braces and parse as JSON."""
    text = path.read_text(encoding="utf-8").strip().rstrip(",")
    return json.loads("{" + text + "}")


def build():
    ajson_files = sorted(SMART_ENV.glob("*.ajson"))
    print(f"Found {len(ajson_files)} .ajson files in {SMART_ENV}")

    vecs = []
    meta = []

    for i, fp in enumerate(ajson_files):
        if i % 1000 == 0:
            print(f"  {i}/{len(ajson_files)} files processed…")
        try:
            data = parse_ajson(fp)
        except Exception as e:
            print(f"  [WARN] Could not parse {fp.name}: {e}")
            continue

        for key, entry in data.items():
            vec = (
                entry.get("embeddings", {})
                .get(MODEL_KEY, {})
                .get("vec")
            )
            if not vec or len(vec) != DIMS:
                continue

            is_source = key.startswith("smart_sources:")
            is_block = key.startswith("smart_blocks:")

            # derive the .md path
            md_path = entry.get("path") or ""
            if not md_path and is_block:
                # block key format: smart_blocks:<file>#<heading>
                md_path = key.split("smart_blocks:")[-1].split("#")[0]

            heading = ""
            lines = None
            if is_block:
                # everything after the first # is the heading
                parts = key.split("#", 1)
                heading = parts[1] if len(parts) > 1 else ""
                lines = entry.get("lines")  # [start, end] 1-based

            em = entry.get("metadata") or {}
            record = {
                "key": key,
                "type": "source" if is_source else "block",
                "path": md_path,
                "heading": heading,
                "lines": lines,
                "title": em.get("title", ""),
                "breadcrumb": em.get("breadcrumb", ""),
                "tags": em.get("tags", []),
                "forms": em.get("forms", []),
                "guide": em.get("guide", ""),
            }
            vecs.append(vec)
            meta.append(record)

    arr = np.array(vecs, dtype=np.float32)
    # L2-normalise so dot product == cosine similarity
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    arr /= norms

    np.save(str(INDEX_NPY), arr)
    INDEX_META.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. {len(meta)} vectors saved.")
    print(f"  Index : {INDEX_NPY}")
    print(f"  Meta  : {INDEX_META}")


if __name__ == "__main__":
    build()
