TASK_DS_EO_012

Title:
Wire PM Role Into Installation and Deployment Pipeline

Role:
Implementer (with CTO oversight)

Context:
The PM role exists in the manifest (`ds_eo_manifest.yaml` roles section, 4th entry),
has a complete `agents/pm.md` persona file (146 lines, comprehensive), and all
protocols reference PM correctly. However, **PM is never wired into any installation
or deployment path**.

Three scripts hardcode exactly 3 roles:

1. `scripts/generate_openclaw_config.sh` — prompts for 3 models, generates agents_list.json
   with only cto/implementer/reviewer (no PM)
2. `scripts/deploy_agents.sh` — copies only cto.md/implementer.md/reviewer.md to workspace
   (`AGENT_FILES=(cto.md implementer.md reviewer.md)`)
3. `scripts/deploy_protocols.sh` — PROTO_FILES list omits `release_management_protocol.md`

Additionally, three test/verification files reference exactly 3 roles:

4. `scripts/verify_installation.sh` — Check 2 asserts `required = ['cto','implementer','reviewer']`,
   Check 4 asserts "All 3 agent prompts present"
5. `tests/test_manifest_schema.py` — `test_roles_count` asserts exactly 3 roles,
   `test_role_ids_present` expects only cto/implementer/reviewer
6. `tests/test_config_merge_safety.py` — expected set is {"cto", "implementer", "reviewer"}

Result: even a fresh DS-EO installation produces openclaw.json with only 3 agents.
PM is ghost-written in the manifest but invisible to users and deployment.

Objective:
Update all three scripts, two test files, and any hardcoded role counts so that PM
is fully wired into the installation pipeline alongside cto/implementer/reviewer.

Acceptance Criteria:
1. `generate_openclaw_config.sh --generate` prompts for a PM model and includes
   a PM entry in agents_list.json
2. `deploy_agents.sh --target <path>` deploys `agents/pm.md` alongside the other 3
3. `deploy_protocols.sh --target <path>` deploys `release_management_protocol.md`
4. `verify_installation.sh` expects and validates 4 roles, not 3
5. `test_manifest_schema.py` test_roles_count expects 4, test_role_ids_present
   expects cto/implementer/reviewer/pm
6. `test_config_merge_safety.py` expected set includes "pm"
7. No hardcoded references to "exactly 3 roles" or "All 3 DS-EO agents" remain
8. All existing tests pass after changes

Constraints:
- Do not modify agent personas (agents/*.md) — they are already correct
- Do not modify protocol files — they already reference PM correctly
- Only modify deployment/installation/verification/test scripts
- Follow standard git conventions for any repo-level changes
