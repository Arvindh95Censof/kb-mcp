# Rebuild the kb-mcp index from all source vaults.
# Re-run after re-embedding any vault in Obsidian Smart Connections.
# After this completes, RESTART the kb-mcp server (it loads the index at startup).

$env:KB_VAULT_DIR    = "C:\Users\CSM-Arvindh\OneDrive - Censof Holdings\Desktop\OPEX\Acumatica-KB"
$env:KB_EXTRA_VAULTS = "GRP=C:\Users\CSM-Arvindh\OneDrive - Censof Holdings\Desktop\OPEX\GRP_UserManuals\GRPUserManuals-Markdown"

& "$PSScriptRoot\.venv\Scripts\python.exe" -m kb_mcp.build_index
