# Uninstalling DS-EO OpenClaw Edition

Complete removal of DS-EO from a host, restoring your OpenClaw configuration to its pre-install state.

---

## Quick Uninstall (Recommended)

### Linux / macOS / WSL2

```bash
bash scripts/uninstall.sh --confirm
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -Confirm
```

Both uninstallers do the same thing: restore `openclaw.json` from backup, clean up protocol files, and remove agent prompt markers. Choose the version that matches your platform.

---

### Options

| Flag | Description |
|------|-------------|
| `--confirm` (bash) / `-Confirm` (PS) | Non-interactive (no prompts) |
| `--dry-run` (bash) / `-DryRun` (PS) | Show what would be removed without making changes |
| `--purge-backups` (bash) / `-PurgeBackups` (PS) | Also remove backup files (use with caution) |

**Preview before uninstalling:**

```bash
# Linux/macOS/WSL2
bash scripts/uninstall.sh --dry-run

# Windows
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -DryRun
```

---

## What Gets Removed

### 1. openclaw.json Agents

DS-EO adds agents to your OpenClaw configuration: `cto`, `implementer`, `reviewer`. The uninstall script restores `openclaw.json` from the backup created during installation.

**Safety**: If no DS-EO backup is found, the script refuses to proceed — you'll be guided through manual removal instead.

### 2. Protocol Files

| Location | What happens |
|----------|--------------|
| `~/.openclaw/protocols/*.md` | Originals restored from `.ds-eo-bak` backups; DS-EO versions removed |
| `<workspace>/docs/development/protocols/` | DS-EO copies removed (originals left alone) |

### 3. Agent Prompts

DS-EO-generated prompt files in `docs/prompts/` are identified by their content (checked for "DS-EO" markers). Non-DS-EO prompt files are never touched.

---

## Platform-Specific Steps

### Scripted Uninstall (default)

#### Linux / macOS / WSL2

```bash
cd /path/to/ds-eo-openclaw
bash scripts/uninstall.sh --confirm
```

After uninstall, restart OpenClaw:

```bash
openclaw gateway restart
```

#### Windows

```powershell
cd C:\path\to\ds-eo-openclaw
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -Confirm
```

After uninstall, restart OpenClaw:

```powershell
openclaw gateway restart
```

Verify agents were removed:

```bash
# Bash (Linux/macOS/WSL2)
python3 -c "import json; d=json.load(open('`$HOME/.openclaw/openclaw.json')); print(len(d.get('agents',{}).get('list',[])))"

# PowerShell (Windows)
python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('agents',{}).get('list',[])))" < `"$env:USERPROFILE\.openclaw\openclaw.json`"
```

Expected output: your original agent count (not 4 with PM added).

### Manual Uninstall (Platform-Neutral)

If the uninstall script is unavailable, follow these steps on any platform. Replace `/path/to/...` with the actual paths for your system.

#### Step 1: Restore openclaw.json from Backup

Find and copy the backup file to restore your original configuration:

**Linux/macOS/WSL2:**
```bash
cp ~/.openclaw/backups/ds-eo-openclaw-LATEST.json.bak ~/.openclaw/openclaw.json
# Or: cp ~/.openclaw/openclaw.json.bak.ds-eo-selfhost ~/.openclaw/openclaw.json
```

**Windows (PowerShell):**
```powershell
Copy-Item "$env:USERPROFILE\.openclaw\backups\ds-eo-openclaw-*.json.bak" -Destination "$env:USERPROFILE\.openclaw\openclaw.json" -Force
# Or: Copy-Item "$env:USERPROFILE\.openclaw\openclaw.json.bak.ds-eo-selfhost" -Destination "$env:USERCLAW\openclaw.json" -Force
```

Verify the restore worked:
```bash
python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json'))" && echo "Valid ✓" || echo "Invalid ✗"
```

#### Step 2: Remove Protocol Files

**Linux/macOS/WSL2:**
```bash
# Restore original protocols from .ds-eo-bak backups
for proto in approval_protocol.md communication_protocol.md completion_protocol.md delegation_protocol.md handoff_protocol.md review_protocol.md; do
    if [ -f ~/.openclaw/protocols/${proto}.ds-eo-bak ]; then
        cp ~/.openclaw/protocols/${proto}.ds-eo-bak ~/.openclaw/protocols/${proto}
        rm ~/.openclaw/protocols/${proto}.ds-eo-bak
    fi
done

# Remove project-level copies
rm -f docs/development/protocols/approval_protocol.md \
      docs/development/protocols/communication_protocol.md \
      docs/development/protocols/completion_protocol.md \
      docs/development/protocols/delegation_protocol.md \
      docs/development/protocols/handoff_protocol.md \
      docs/development/protocols/review_protocol.md

# Remove any leftover DS-EO markers
find ~/.openclaw -name "*.ds-eo-bak" -delete 2>/dev/null || true
```

**Windows (PowerShell):**
```powershell
$protos = @('approval_protocol','communication_protocol','completion_protocol','delegation_protocol','handoff_protocol','review_protocol')
foreach ($p in $protos) {
    $src = "$env:USERPROFILE\.openclaw\protocols\$p.md.ds-eo-bak"
    if (Test-Path $src) {
        Copy-Item $src -Destination "$env:USERPROFILE\.openclaw\protocols\$p.md" -Force
        Remove-Item $src -Force -ErrorAction SilentlyContinue
    }
}

# Remove project-level copies
$projProtos = @('approval_protocol','communication_protocol','completion_protocol','delegation_protocol','handoff_protocol','review_protocol')
foreach ($p in $protos) {
    $path = "docs\development\protocols\$p.md"
    if (Test-Path $path) { Remove-Item $path -Force -ErrorAction SilentlyContinue }
}

# Clean up leftover DS-EO markers
Get-ChildItem "$env:USERPROFILE\.openclaw" -Recurse -Filter "*.ds-eo-bak" -ErrorAction SilentlyContinue | Remove-Item -Force
```

#### Step 3: Remove Agent Prompt Files (if applicable)

**Linux/macOS/WSL2:**
```bash
grep -l 'DS-EO\|ds-eo-openclaw' docs/prompts/*.md 2>/dev/null | xargs rm -f 2>/dev/null || true
```

**Windows (PowerShell):**
```powershell
Get-ChildItem "docs\prompts\*.md" -ErrorAction SilentlyContinue | Where-Object {
    (Get-Content $_.FullName -Raw) -match 'DS-EO|ds-eo-openclaw'
} | Remove-Item -Force -ErrorAction SilentlyContinue
```

---

## Rollback / Troubleshooting

### Uninstall broke something?

The backup is always preserved (unless `--purge-backups` was used). Restore manually:

**Linux/macOS/WSL2:**
```bash
cp ~/.openclaw/openclaw.json.bak.ds-eo-selfhost ~/.openclaw/openclaw.json
# Or the latest timestamped backup:
cp $(ls -t ~/.openclaw/backups/ds-eo-openclaw-*.json.bak | head -1) ~/.openclaw/openclaw.json
```

**Windows (PowerShell):**
```powershell
Copy-Item "$env:USERPROFILE\.openclaw\openclaw.json.bak.ds-eo-selfhost" -Destination "$env:USERPROFILE\.openclaw\openclaw.json" -Force
# Or latest backup:
$latest = Get-ChildItem "$env:USERPROFILE\.openclaw\backups\ds-eo-openclaw-*.json.bak" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Copy-Item $latest.FullName -Destination "$env:USERPROFILE\.openclaw\openclaw.json" -Force
```

### "No backup found" error?

This means neither `openclaw.json.bak.ds-eo-selfhost` nor any timestamped backup exists. Options:

1. **Check other hosts** — if you moved DS-EO between machines, the backup may be on the source host
2. **Manual removal** — edit `~/.openclaw/openclaw.json` directly to remove DS-EO agent entries
3. **Reinstall then uninstall** — run `bash scripts/uninstall.sh --confirm` (or the `.ps1` equivalent), then re-run the uninstall

### Verify clean state after uninstall

```bash
# Should show your original agent count (not 4)
python3 -c "import json; d=json.load(open('`$HOME/.openclaw/openclaw.json')); print(len(d.get('agents',{}).get('list',[])))"

# No DS-EO protocol files should remain
ls ~/.openclaw/protocols/*.ds-eo-bak 2>/dev/null | wc -l  # Should be 0

# openclaw.json should be valid JSON
python3 -c "import json; json.load(open('`$HOME/.openclaw/openclaw.json'))" && echo "Valid JSON ✓"
```

---

## Complete Host Wipe (Nuclear Option)

If you want to remove everything — package, configs, backups:

**Linux/macOS/WSL2:**
```bash
# 1. Uninstall cleanly first
bash scripts/uninstall.sh --confirm --purge-backups

# 2. Remove the DS-EO package directory
rm -rf /path/to/ds-eo-openclaw

# 3. Clean any remaining DS-EO traces
find ~/.openclaw -name "*ds-eo*" -delete 2>/dev/null || true
```

**Windows (PowerShell):**
```powershell
# 1. Uninstall cleanly first
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -Confirm -PurgeBackups

# 2. Remove the DS-EO package directory
Remove-Item -Recurse -Force C:\path\to\ds-eo-openclaw

# 3. Clean any remaining DS-EO traces
Get-ChildItem "$env:USERPROFILE\.openclaw" -Recurse -Filter "*ds-eo*" -ErrorAction SilentlyContinue | Remove-Item -Force
```

⚠️ **Warning**: This is irreversible. Only use if you're sure you want to completely remove DS-EO from this host.

---

*DS-EO OpenClaw Edition — Production Readiness (Phase 3)*
