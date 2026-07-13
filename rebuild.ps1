# Rebuild the kb-mcp index from all source vaults.
# Re-run after re-embedding any vault in Obsidian Smart Connections.
# After this completes, RESTART the kb-mcp server (it loads the index at startup).

$env:KB_VAULT_DIR    = "C:\Users\CSM-Arvindh\OneDrive - Censof Holdings\Desktop\OPEX\Acumatica-KB"
# Extra GRP-manuals vault dropped 2026-07-06: the updated + split GRP manuals now
# live INSIDE the primary Acumatica-KB vault, so the old raw folder would only add
# stale duplicates. Set empty to override any inherited value.
$env:KB_EXTRA_VAULTS = ""

& "$PSScriptRoot\.venv\Scripts\python.exe" -m kb_mcp.build_index
