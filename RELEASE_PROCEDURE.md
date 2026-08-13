# DS-EO Release Procedure

## How to Create a Release

Releases are created via GitHub Actions — **no local commands required**.

### Step 1: Go to the Releases tab

```
https://github.com/Deepsim-AI/DS-EO/actions/workflows/release.yml
```

Click **"Run workflow"** → select branch **main** → choose your semver type.

### Step 2: Choose release type

| Type | What it does | When to use |
|------|-------------|-------------|
| `patch` | Bumps `0.x.Y` → `0.x.(Y+1)` | Bug fixes, no new features |
| `minor` | Bumps `0.X.y` → `0.(X+1).0` | New features, backward-compatible |
| `major` | Bumps `X.y.z` → `(X+1).0.0` | Breaking changes |

The version number is read from `ds_eo_manifest.yaml`. The workflow will:

1. Validate the repository and run all tests (23+ test files)
2. Bump version in `ds_eo_manifest.yaml` + `ds_eo_openclaw/__init__.py`
3. Commit, push to main, create git tag, publish GitHub Release
4. Generate release notes from commit history

### Step 3: Verify the release

After the workflow completes (green checkmark):

- Git tag exists: `git tag -l 'v*'`
- GitHub Release published at `https://github.com/Deepsim-AI/DS-EO/releases`
- README.md roadmap updated (done as part of normal dev)

### Safety guarantees

- **Tests must pass** before any version change is committed — failed tests abort the entire workflow with no push, tag, or release.
- **Duplicate tags are prevented** — the workflow checks for existing tags before proceeding.
- **Tag + Release creation are chained** — if the git tag push fails, the GitHub Release is never created.
- **Workflow only triggers manually** — ordinary pushes/PRs do not trigger releases.

### Version conventions

- The project uses semver (`MAJOR.MINOR.PATCH`)
- `ds_eo_manifest.yaml` is the single source of truth for the version number
- Python package `__init__.py` is synchronized from the manifest by the workflow
- CHANGELOG.md entries are preserved as-is (mixed format: `[vX.Y.Z]` and `## TASK_DS_EO_XXX`)

### Troubleshooting

**"Tag already exists" error**: A previous partial release may have created the tag. Delete it locally and remotely, then re-run:
```bash
git tag -d v0.X.Y
git push origin :refs/tags/v0.X.Y   # remote delete
# Then re-run the workflow
```

**Tests failing before release**: Fix the failing tests in a separate commit on main, then retry the release.
