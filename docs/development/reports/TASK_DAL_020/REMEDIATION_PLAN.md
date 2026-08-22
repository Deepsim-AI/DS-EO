# TASK_DAL_020 — Remediation Plan

## Current State (Verified)

### Issues Found:
1. **functions.php** - Still has wrong CSS path: `/task-dal-016.css` instead of `/assets/css/task-dal-016.css`
2. **Nested directories** - `deepsim-lab/deepsim-lab/` exists and needs removal
3. **HTTP verification** - CSS returns 404 due to wrong path
4. **Verification script** - `verify-dal-017-deployment.sh` does not exist

### What Was Prepared:
- ✅ Fixed functions.php ready at `/tmp/functions.php.fixed`
- ✅ Verification script ready at `/tmp/final_verification.sh`

## Required Actions (Need Sudo)

### 1. Fix functions.php
```bash
sudo cp /tmp/functions.php.fixed /home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/functions.php
```

### 2. Remove Nested Directories
```bash
sudo rm -rf /home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/deepsim-lab
```

### 3. Verify Changes
```bash
/tmp/final_verification.sh
```

## Expected Outcome

After applying fixes:
- functions.php will reference `/assets/css/task-dal-016.css`
- CSS will return HTTP 200
- All 14 SVG assets will be accessible
- Nested directories will be removed
- Verification script will pass all checks

## Status

**AWAITING USER ACTION**: Need sudo privileges to complete the fixes.

The forensic audit confirmed that TASK_DAL_019 was NOT completed successfully. The fix scripts are prepared and ready to execute with sudo privileges.