# TASK_DAL_018 - Remaining Fixes Required

## Current State
- DAL-016 CSS exists at: `/home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/assets/css/task-dal-016.css`
- CSS returns HTTP 200 ✓
- functions.php still references: `/task-dal-016.css` (wrong path)
- Homepage contains: `neural-network.svg` and `footer-atom.svg`
- Nested directories exist: `deepsim-lab/deepsim-lab/` and `deepsim-lab/deepsim-lab/deepsim-lab/`

## Required Fixes

### 1. Fix CSS Enqueue Path in functions.php
**File**: `/home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/functions.php`
**Line 28**: Change from:
```php
wp_enqueue_style('deepsim-visual', get_template_directory_uri() . '/task-dal-016.css', ['deepsim-pages'], '0.1.0');
```
To:
```php
wp_enqueue_style('deepsim-visual', get_template_directory_uri() . '/assets/css/task-dal-016.css', ['deepsim-pages'], '0.1.0');
```

### 2. Remove Nested Directories
**Directories to remove**:
- `/home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/deepsim-lab/`
- `/home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/deepsim-lab/deepsim-lab/`

**Command**:
```bash
sudo rm -rf /home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/deepsim-lab
```

### 3. Fix File Permissions
**Command**:
```bash
sudo chown deepsim:deepsim /home/deepsim/deepsim-ai-lab/wp-content/themes/deepsim-lab/functions.php
```

## Verification Steps

After applying fixes:

1. **Test CSS URL**: Visit `http://localhost/wp-content/themes/deepsim-lab/assets/css/task-dal-016.css` - should return HTTP 200

2. **Test Homepage**: Visit `http://localhost` - should load with DAL-016 styling

3. **Verify SVG References**: Check that homepage references `neural-network.svg` and `footer-atom.svg` correctly

## Status
**Implementation artifacts generated; deployment/integration failed verification.**

All fixes are documented and ready for execution with sudo privileges.