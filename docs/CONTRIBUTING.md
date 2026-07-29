# Contributing to DS-EO OpenClaw Edition

## Development Setup

1. Clone the repository:
   ```bash
   git clone <repo-url> ds-eo-openclaw
   cd ds-eo-openclaw
   ```

2. Run tests to verify setup:
   ```bash
   # Install dependencies
   pip install pyyaml pytest

   # Run all tests
   python3 -m pytest tests/
   bash tests/test_installation_flow.sh
   ```

## Project Structure

See [README.md](../README.md#repository-structure) for the full directory layout.

Key areas:

| Area | Purpose | When to Modify |
|------|---------|----------------|
| `agents/*.md` | Role prompt definitions | Adding roles, updating responsibilities |
| `protocols/*.md` | Engineering protocols | Updating workflow rules, gates, message formats |
| `templates/` | Document templates | Adding/changing report or spec formats |
| `scripts/` | Installation helpers | Installer changes, new deployment options |
| `tests/` | Verification suite | Adding new checks, fixing test failures |
| `ds_eo_manifest.yaml` | Package manifest (source of truth) | Any structural change to the package |

## Making Changes

### Updating a Protocol

1. Edit the protocol file in `protocols/`
2. Update any references in `ds_eo_manifest.yaml` if gate definitions change
3. Run tests: `python3 -m pytest tests/test_protocol_extraction.py`
4. Update documentation if user-facing behavior changes

### Adding a New Role

1. Add role definition to `agents/<name>.md`
2. Add entry to `ds_eo_manifest.yaml` under `roles:` section
3. Add config template entry to `config-templates/example_openclaw_config.json`
4. Update `scripts/generate_openclaw_config.sh` if the new role needs special handling
5. Run full test suite: `python3 -m pytest tests/ && bash tests/test_installation_flow.sh`

### Updating Installation Scripts

1. Modify scripts in `scripts/`
2. Test on a clean OpenClaw instance (not your production setup)
3. Update `INSTALLATION.md` with new steps or options
4. Run smoke test: `bash tests/test_installation_flow.sh`

## Code Style

- **Shell scripts**: Bash, `set -euo pipefail`, quoted variables, descriptive comments
- **Python tests**: unittest framework, docstrings for classes, clear assertions
- **Markdown**: Consistent heading hierarchy, tables where appropriate, no trailing whitespace
- **YAML manifest**: Comments explaining non-obvious fields, consistent indentation

## Testing Standards

All changes must pass:
1. `python3 -m pytest tests/` — unit and schema validation tests
2. `bash tests/test_installation_flow.sh` — end-to-end smoke test on clean environment

For protocol or template changes, also verify with:
- Manual installation on a test OpenClaw instance
- A complete task cycle using the new components

## Pull Request Process

1. Fork and branch from `main`
2. Make changes following the style guide above
3. Run all tests locally
4. Update documentation if user-facing behavior changes
5. Submit PR with description of what changed and why

## License

MIT — see [ds_eo_manifest.yaml](../ds_eo_manifest.yaml) for details.
