# Upgrading DS-EO OpenClaw Edition

Complete guide for upgrading between versions of DS-EO.

---

## Upgrade Path

| From | To | Method | Status |
|------|-----|--------|--------|
| v0.1.x | v0.2.x | `scripts/migrate_to_v0.2.sh` | ✅ Supported |
| v0.2.x | v1.0+ | Manual migration (see below) | 🚧 Planned |

---

## Upgrading from v0.1 to v0.2

### What's New in v0.2

**Ecosystem Planning Phase** — This version focuses on:
- Cross-host deployment testing
- Task volume validation (3–5 real tasks)
- Protocol refinement based on production use
- Multi-platform compatibility analysis (Claude, Codex, Gemini editions)

### Changes Between v0.1 and v0.2

#### Breaking Changes

**None.** v0.2 is a non-breaking upgrade focused on ecosystem planning and validation.

#### Improvements

| Component | Change | Impact |
|-----------|--------|--------|
| Agent Config | Added `profile` field to implementer agent (coding profile) | New tool access profile for coding tasks |
| Manifest | Version bumped to 0.2.0 | Tracks upgrade progress |
| Documentation | Enhanced uninstall and conflict detection procedures | Better operational safety |

#### No Protocol Changes

The core protocol files remain unchanged in v0.2. All existing protocol formats are preserved.

---

### Automated Upgrade (Recommended)

DS-EO provides an automated migration script that handles all changes safely:

```bash
# Preview what will change (dry-run mode)
cd /path/to/ds-eo-openclaw
bash scripts/migrate_to_v0.2.sh --dry-run

# Apply the upgrade
bash scripts/migrate_to_v0.2.sh
```

**What the script does:**

1. **Detects current version** from `ds_eo_manifest.yaml` or config file
2. **Validates compatibility** — ensures you're upgrading from v0.1.x to v0.2.x
3. **Identifies required changes**:
   - Adds `profile: coding` field to implementer agent in `openclaw.json`
   - Updates version in `ds_eo_manifest.yaml` from 0.1.x → 0.2.0
4. **Backs up before each modification** — creates `.bak.pre-migrate-v0.2` files
5. **Verifies migration** — confirms changes were applied correctly

**Safety features:**

- ✅ Always creates backups before modifying files
- ✅ Dry-run mode shows changes without applying them
- ✅ Idempotent — running again detects you're already on v0.2 and exits cleanly
- ✅ Rollback procedure documented in post-migration output

**After upgrade:**

```bash
# Restart OpenClaw to load new config
openclaw gateway restart

# Verify agents loaded correctly
cat ~/.openclaw/openclaw.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['agents']['list']), 'agents loaded')"
```

---

### Manual Upgrade (Advanced)

If you prefer manual control or the automated script fails:

#### 1. Backup Everything First

```bash
# Create a comprehensive backup
mkdir -p ~/ds-eo-backup-$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=~/ds-eo-backup-$(date +%Y%m%d-%H%M%S)

cp ~/.openclaw/openclaw.json "$BACKUP_DIR/"
cp /path/to/ds-eo-openclaw/ds_eo_manifest.yaml "$BACKUP_DIR/"
# Copy any other modified files you're aware of
```

#### 2. Update openclaw.json

Add the `profile` field to the implementer agent:

```json
{
  "id": "implementer",
  "name": "Code Implementer",
  "model": "ollama/qwen3.8:27b",
  "profile": "coding",  // ← Add this line
  "tools": { ... }
}
```

#### 3. Update Manifest Version

In `ds_eo_manifest.yaml`, change:

```yaml
version: "0.1.0"
```

to:

```yaml
version: "0.2.0"
```

#### 4. Verify and Restart

```bash
# Validate JSON syntax
python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json'))" && echo "Valid ✓"

# Restart OpenClaw
openclaw gateway restart
```

---

## Rollback Procedure

If the upgrade causes issues, you can roll back to v0.1:

### Automated Rollback (v0.2 → v0.1)

The migration script preserves backups with `.bak.pre-migrate-v0.2` suffix:

```bash
# Restore openclaw.json from backup
cp ~/.openclaw/openclaw.json.bak.pre-migrate-v0.2 ~/.openclaw/openclaw.json

# Restore manifest version (if you want to revert that too)
cd /path/to/ds-eo-openclaw
sed -i 's/version: "0.2.0"/version: "0.1.0"/' ds_eo_manifest.yaml

# Restart OpenClaw
openclaw gateway restart
```

### Manual Rollback (from any backup)

If the automated backup is missing, restore from your pre-upgrade backup:

```bash
BACKUP_DIR=~/ds-eo-backup-YYYYMMDD-HHMMSS
cp "$BACKUP_DIR/openclaw.json" ~/.openclaw/openclaw.json
# Restore other files as needed
openclaw gateway restart
```

---

## Troubleshooting

### "Cannot detect current DS-EO version"

The script couldn't find a version indicator. This usually means:

1. **Not actually installed** — You may be running a fresh install, not an upgrade
2. **Manifest missing** — `ds_eo_manifest.yaml` doesn't exist in the package root
3. **Corrupted manifest** — YAML syntax error preventing parsing

**Solution:** Check if you're on v0.1 by looking for the old config structure (no `profile` field in implementer agent). If confirmed, you can manually apply the changes listed above.

### "Incompatible version: X.Y.Z"

You're trying to upgrade from a version not supported by this migration script. Currently only v0.1.x → v0.2.x is supported.

**Solution:** For other versions, consult the release notes or perform manual migration based on the documented changes.

### Migration applied but agents don't work after restart

Possible causes:

1. **Model not available** — The new profile may require a different model
2. **Config syntax error** — JSON became invalid during edit
3. **OpenClaw cache** — Old config cached in memory

**Solution:**

```bash
# Validate JSON
python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json'))" && echo "Valid ✓" || echo "Invalid ✗"

# Check agent count
python3 -c "import json; d=json.load(open('$HOME/.openclaw/openclaw.json')); print(len(d['agents']['list']), 'agents')"

# Clear OpenClaw cache and restart
openclaw gateway restart --force
```

---

## Future Upgrades (v0.2 → v1.0+)

The roadmap indicates v1.0 will introduce a **Platform Abstraction Layer** with significant changes:

- Agent config schema updates for cross-platform compatibility
- Protocol format standardization across editions
- New installation mechanisms (potentially ClawHub-based)

**Recommendation:** When v1.0 ships, use the provided migration tool rather than manual upgrade to ensure all platform-specific adjustments are applied correctly.

---

## Version History

| Version | Date | Changes | Migration Required |
|---------|------|---------|-------------------|
| 0.2.0 | 2026-07-28 | Ecosystem planning, profile field added, enhanced safety procedures | `migrate_to_v0.2.sh` (automated) |
| 0.1.0 | Initial | Self-hosting completion, core agent/protocol framework | N/A (initial install) |

---

*DS-EO OpenClaw Edition — Production Readiness (Phase 3)*
