# CTO Plan — TASK_DS_EO_012

**Task**: TASK_DS_EO_012  
**agent_id**: cto  
**session_id**: _(filled at execution time)_  
**model**: ollama/qwen3.6:35b  
**produced_at**: 2026-07-30T09:40PDT  

---

## Problem Statement

PM role exists as a ghost entry in `ds_eo_manifest.yaml` and has a complete
`agents/pm.md` persona, but three deployment scripts and two test files still
hardcode exactly 3 roles. A fresh DS-EO installation produces openclaw.json
with only CTO/Implementer/Reviewer — PM never appears.

This is the concrete failure that motivated returning to TASK_DS_EO_007:
the plan was sound, but the follow-through (installation wiring) was never done.

---

## Root Cause Analysis

| # | File | Hardcoded Value | Should Be |
|---|------|-----------------|-----------|
| 1 | `generate_openclaw_config.sh` — prompt for PM model | Missing (no PM prompt) | Add PM model prompt |
| 2 | `generate_openclaw_config.sh` — Python agents list | 3 entries (cto/implementer/reviewer) | 4 entries + pm entry |
| 3 | `deploy_agents.sh` — AGENT_FILES array | `(cto.md implementer.md reviewer.md)` | Add `pm.md` |
| 4 | `deploy_protocols.sh` — PROTO_FILES list | 7 files, no release_management | Add `release_management_protocol.md` |
| 5 | `verify_installation.sh` Check 2 | `required = ['cto','implementer','reviewer']` | Add `'pm'` |
| 6 | `verify_installation.sh` messages | "All 3 DS-EO agents" / "All 3 agent prompts" | Update to 4 |
| 7 | `test_manifest_schema.py` — test_roles_count | `self.assertEqual(len(roles), 3, ...)` | Expect 4 |
| 8 | `test_manifest_schema.py` — test_role_ids_present | `{"cto","implementer","reviewer"}` | Add `"pm"` |
| 9 | `test_manifest_schema.py` — test_each_role_has_required_fields | Requires `model_placeholder` field | PM role lacks it (needs one) |
| 10 | `test_config_merge_safety.py` expected set | `{"cto","implementer","reviewer"}` | Add `"pm"` |

### Note on §9 of TASK_DS_EO_007: Step P0-2 Missing `model_placeholder`

TASK_DS_EO_007's CTO_PLAN.md proposed PM with:
```yaml
default_model: "ollama/qwen3.6:35b"
tool_profile: "generic"
```
But **no `model_placeholder`**. The existing 3 roles all have `model_placeholder`
(`<MODEL_CTO>`, `<MODEL_IMPLEMENTER>`, `<MODEL_REVIEWER>`), and the test in
`test_manifest_schema.py` (`test_each_role_has_required_fields`) validates this
field is present on every role. **PM needs a `model_placeholder` entry.**

---

## Work Items (in execution order)

### Item 1: Add `model_placeholder` to PM role in manifest

**File**: `ds_eo_manifest.yaml`  
**Action**: Add `model_placeholder: "<MODEL_PM>"` to the pm role entry.

```diff
   - id: "pm"
     name: "Project Manager"
     emoji: "📋"
     prompt_file: "agents/pm.md"
     description: "Process oversight — task lifecycle, status tracking, release management."
+    model_placeholder: "<MODEL_PM>"       # User fills this in during install
     default_model: "ollama/qwen3.6:35b"
     tool_profile: "generic"
```

### Item 2: Wire PM into `generate_openclaw_config.sh`

**File**: `scripts/generate_openclaw_config.sh`  
**Changes**: Two modifications to the `--generate` block.

**Change 2a — Add PM model prompt** (after Reviewer prompt, before workspace path):
```bash
    # PM Model
    read -r -p "  PM model [ollama/qwen3.6:35b]: " pm_model
    pm_model="${pm_model:-ollama/qwen3.6:35b}"
```

**Change 2b — Add PM entry to Python agents list** (after reviewer entry):
```python
    {
        'default': False,
        'id': 'pm',
        'name': 'Project Manager',
        'identity': {'emoji': '\U0001f4cb', 'name': 'PM'},
        'model': sys.argv[3],          # <-- becomes argv[3]
        'workspace': sys.argv[5],      # <-- becomes argv[5]
        'tools': {
            'allow': ['group:fs','web_search','web_fetch'],
            'deny': ['write','edit','apply_patch','exec','process']
        }
    }
```

**Argv shift**: All existing `sys.argv[N]` references in the --generate block
need adjustment since we add one more prompt:
- argv[1]: cto_model (unchanged)
- argv[2]: impl_model (unchanged)  
- argv[3]: rev_model → **becomes** argv[4]
- argv[4]: pm_model → **new**, **becomes** argv[5]

This is the trickiest change. Carefully update all `sys.argv[N]` references
in both the `agents` list construction and the output message at the bottom.

### Item 3: Wire PM into `deploy_agents.sh`

**File**: `scripts/deploy_agents.sh`  
**Change**: Add `pm.md` to AGENT_FILES array.

```diff
-AGENT_FILES=(cto.md implementer.md reviewer.md)
+AGENT_FILES=(cto.md implementer.md pm.md reviewer.md)
```

### Item 4: Wire PM protocol into `deploy_protocols.sh`

**File**: `scripts/deploy_protocols.sh`  
**Change**: Add `release_management_protocol.md` to PROTO_FILES array.

```diff
 PROTOCOL_FILES=(
     approval_protocol.md
     communication_protocol.md
     completion_protocol.md
     delegation_protocol.md
     handoff_protocol.md
     implementation_protocol.md
-    review_protocol.md
+    release_management_protocol.md
+    review_protocol.md
 )
```

### Item 5: Update `verify_installation.sh`

**File**: `scripts/verify_installation.sh`  
**Changes**: Three modifications.

**Change 5a — Check 2 required list**: Add `'pm'`:
```diff
     agents_list = config.get('agents', {}).get('list', [])
     agent_ids = [a.get('id','') for a in agents_list]
-    required = ['cto','implementer','reviewer']
+    required = ['cto','implementer','pm','reviewer']
```

**Change 5b — Pass message**: Update count:
```diff
-        check_pass "All 3 DS-EO agents present in openclaw.json"
+        check_pass "All 4 DS-EO agents present in openclaw.json"
```

**Change 5c — Check 4 agent list**: Add `pm.md`:
```diff
     # Verify each agent file exists and is non-empty
-    AGENT_FILES=(cto.md implementer.md reviewer.md)
+    AGENT_FILES=(cto.md implementer.md pm.md reviewer.md)
```

**Change 5d — Pass message for Check 4**: Update count:
```diff
         check_pass "All 3 agent prompts present and non-empty in package"
+        check_pass "All 4 agent prompts present and non-empty in package"
```

### Item 6: Update `test_manifest_schema.py`

**File**: `tests/test_manifest_schema.py`  
**Changes**: Two test methods.

**Change 6a — test_roles_count**:
```diff
     def test_roles_count(self):
         roles = self.manifest.get("roles", [])
-        self.assertEqual(len(roles), 3, f"Expected exactly 3 roles, got {len(roles)}")
+        self.assertEqual(len(roles), 4, f"Expected exactly 4 roles, got {len(roles)}")
```

**Change 6b — test_role_ids_present**:
```diff
     def test_role_ids_present(self):
         role_ids = {r["id"] for r in self.manifest.get("roles", [])}
-        expected = {"cto", "implementer", "reviewer"}
+        expected = {"cto", "implementer", "pm", "reviewer"}
         self.assertEqual(role_ids, expected, f"Role IDs: got {role_ids}, expected {expected}")
```

### Item 7: Update `test_config_merge_safety.py`

**File**: `tests/test_config_merge_safety.py`  
**Change**: Add "pm" to expected set.

```diff
-        expected = {"cto", "implementer", "reviewer"}
+        expected = {"cto", "implementer", "pm", "reviewer"}
```

---

## Acceptance Criteria Verification Plan

After implementation, verify:

1. `bash scripts/generate_openclaw_config.sh --generate` — prompts for 4 models (CTO, Implementer, Reviewer, PM), outputs agents_list.json with 4 entries including pm
2. `bash scripts/deploy_agents.sh --target /tmp/test-agents/` — deploys all 4 agent files
3. `bash scripts/deploy_protocols.sh --target /tmp/test-protocols/` — deploys all 8 protocol files including release_management_protocol.md
4. `bash scripts/verify_installation.sh` — passes with "All 4 DS-EO agents present" and "All 4 agent prompts present"
5. `python3 -m pytest tests/test_manifest_schema.py -v` — test_roles_count expects 4 ✓, test_role_ids_present includes pm ✓
6. `python3 -m pytest tests/test_config_merge_safety.py -v` — expected set includes pm ✓
7. Full test suite passes: `python3 -m pytest tests/ -v`

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Python argv indices shift in generate_openclaw_config.sh introduces off-by-one bugs | **High** | Add explicit comments mapping each sys.argv[i] to its source; test with --generate and verify JSON output |
| deploy_protocols.sh rollback mode now also handles release_management_protocol.md — rollback must handle it too | Medium | PROTO_FILES array controls both deploy and rollback, so adding one entry fixes both automatically (single source of truth) |
| Existing installations on disk have PM role in manifest but not deployed | Low (document only) | This is the current state. New installs after this fix will be correct. No migration needed since PM is opt-in (model_prompt during install). |

---

## What NOT to Change

- **agents/pm.md** — persona file is complete and correct
- **protocols/** — all protocols already reference PM correctly
- **ds_eo_manifest.yaml roles structure** — pm role entry exists; only adding model_placeholder
- **Protocol content** — release_management_protocol.md, handoff_protocol.md, etc. are already written

---

## Gate Decision

**APPROVED TO PROCEED** — This is a straightforward wiring fix with no architectural changes. The PM persona and protocol definitions are correct (established in TASK_DS_EO_007 / commit 489a03a). The only gap was deployment/installation scripts still hardcoding 3 roles, which this plan closes completely across all 10 identified locations.

---

*Planned by: CTO Agent (ollama/qwen3.6:35b)*  
*Gate: G1 — Plan Approval*
