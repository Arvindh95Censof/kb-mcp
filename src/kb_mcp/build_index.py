"""
build_index.py  —  run this once to parse all .ajson embeddings and save a
numpy index + metadata JSON that the MCP server loads at startup.

Usage:
    python -m kb_mcp.build_index

Vaults ingested:
    1. Primary  — KB_VAULT_DIR (defaults to sibling ../Acumatica-KB).
    2. Extra    — KB_EXTRA_VAULTS, a ';'-separated list of  LABEL=PATH  pairs,
                  e.g.  "GRP=C:\\...\\GRPUserManuals-Markdown".
                  Each extra vault's records get guide=LABEL and an absolute
                  'vault_root' baked in, so the server can read their files
                  without any extra env configuration.

Outputs (written next to this script's package, or to KB_MCP_INDEX_DIR env var):
    kb_index.npy      — float32 array of shape (N, 384), L2-normalised
    kb_meta.json      — list of N metadata dicts
"""

import json
import os
import sys
import numpy as np
from pathlib import Path

MODEL_KEY = "TaylorAI/bge-micro-v2"
DIMS = 384

INDEX_DIR = Path(os.environ.get("KB_MCP_INDEX_DIR", Path(__file__).resolve().parent))
INDEX_NPY = INDEX_DIR / "kb_index.npy"
INDEX_META = INDEX_DIR / "kb_meta.json"


def _primary_vault() -> Path:
    vd = Path(os.environ.get("KB_VAULT_DIR", ""))
    if vd and vd.exists():
        return vd
    here = Path(__file__).resolve().parent
    mcps_dir = here.parent.parent.parent  # kb-mcp's parent
    desktop_dir = mcps_dir.parent
    for candidate in (desktop_dir / "OPEX" / "Acumatica-KB", mcps_dir / "Acumatica-KB"):
        if candidate.exists():
            return candidate
    sys.exit("Cannot locate vault. Set KB_VAULT_DIR env var to the Acumatica-KB folder.")


def get_vaults() -> list[dict]:
    """Return a list of {root, guide_override, is_primary} dicts."""
    vaults = [{"root": _primary_vault(), "guide_override": None, "is_primary": True}]
    extra = os.environ.get("KB_EXTRA_VAULTS", "").strip()
    for part in extra.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        label, p = part.split("=", 1)
        root = Path(p.strip())
        if not root.exists():
            print(f"  [WARN] extra vault not found, skipping: {root}")
            continue
        vaults.append({"root": root, "guide_override": label.strip(), "is_primary": False})
    return vaults


def parse_ajson(path: Path) -> dict:
    """Wrap the bare key:value pairs in braces and parse as JSON."""
    text = path.read_text(encoding="utf-8").strip().rstrip(",")
    return json.loads("{" + text + "}")


def ingest_vault(vault: dict, vecs: list, meta: list) -> int:
    root = vault["root"]
    smart_env = root / ".smart-env" / "multi"
    if not smart_env.exists():
        print(f"  [WARN] no .smart-env/multi in {root}, skipping")
        return 0
    ajson_files = sorted(smart_env.glob("*.ajson"))
    label = vault["guide_override"] or "(primary)"
    print(f"Vault {label}: {len(ajson_files)} .ajson files in {smart_env}")

    added = 0
    for i, fp in enumerate(ajson_files):
        if i % 1000 == 0 and i:
            print(f"  {i}/{len(ajson_files)} files…")
        try:
            data = parse_ajson(fp)
        except Exception as e:
            print(f"  [WARN] Could not parse {fp.name}: {e}")
            continue

        for key, entry in data.items():
            if not isinstance(entry, dict):
                continue
            vec = entry.get("embeddings", {}).get(MODEL_KEY, {}).get("vec")
            if not vec or len(vec) != DIMS:
                continue

            is_source = key.startswith("smart_sources:")
            is_block = key.startswith("smart_blocks:")
            if not (is_source or is_block):
                continue

            md_path = entry.get("path") or ""
            if not md_path and is_block:
                md_path = key.split("smart_blocks:")[-1].split("#")[0]

            # skip Obsidian plugin cruft (e.g. Copilot custom-prompt templates)
            if md_path.replace("\\", "/").startswith("copilot/"):
                continue

            heading = ""
            if is_block:
                parts = key.split("#", 1)
                heading = parts[1] if len(parts) > 1 else ""
            lines = entry.get("lines")

            em = entry.get("metadata") or {}
            guide = vault["guide_override"] or em.get("guide", "")
            # for extra vaults with no frontmatter, synthesize a title from filename
            title = em.get("title", "")
            if not title and not vault["is_primary"] and md_path:
                title = Path(md_path).stem

            record = {
                "key": key,
                "type": "source" if is_source else "block",
                "path": md_path,
                "heading": heading,
                "lines": lines,
                "title": title,
                "breadcrumb": em.get("breadcrumb", ""),
                "tags": em.get("tags", []),
                "forms": em.get("forms", []),
                "guide": guide,
            }
            # primary vault reads relative to KB_VAULT_DIR (back-compat: no vault_root);
            # extra vaults bake an absolute root so the server needs no extra env.
            if not vault["is_primary"]:
                record["vault_root"] = str(root)

            vecs.append(vec)
            meta.append(record)
            added += 1
    print(f"  -> {added} vectors from {label}")
    return added


def build():
    vaults = get_vaults()
    vecs: list = []
    meta: list = []
    for v in vaults:
        ingest_vault(v, vecs, meta)

    arr = np.array(vecs, dtype=np.float32)
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
