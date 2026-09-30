"""Utility functions for /eo mode slash commands.

Wraps the existing ModeSelector API with clean function interfaces
for use by the OpenClaw skill handler.
"""

from ds_eo_openclaw.workflow.selector import ModeSelector, create_selector
from ds_eo_openclaw.workflow.config import WorkflowConfig


def get_current_mode() -> dict:
    """Returns current execution mode and task overrides.
    
    Returns:
        dict with keys:
            - 'execution_mode': str (current global mode)
            - 'task_overrides': dict (task_id → mode mapping, may be empty)
    """
    selector = create_selector()
    return {
        'execution_mode': selector.get_current_mode(),
        'task_overrides': selector.config.task_overrides.copy()
    }


def switch_to(mode: str) -> tuple[bool, str]:
    """Switch global execution mode via ModeSelector.
    
    Args:
        mode: Target mode ('manual' or 'automatic')
        
    Returns:
        Tuple of (success: bool, message: str)
            - success=True → switch completed with confirmation message
            - success=False → invalid mode, message contains error details
    """
    selector = create_selector()
    
    # Validate mode first — ModeSelector.switch_mode raises ValueError on invalid input
    if mode not in ('manual', 'automatic'):
        return (False, f"❌ Invalid execution mode '{mode}'. Must be one of: manual, automatic")
    
    try:
        old_mode, new_mode, notification = selector.switch_mode(mode)
        
        # Build confirmation message per architecture §6.3 format
        if old_mode == new_mode:
            message = f"ℹ️  Execution mode already set to {new_mode}"
        else:
            message = f"✅ Execution mode changed: {old_mode} → {new_mode}\n\n{notification}"
        
        # Add note about G1/G4 gate behavior (per D4 architecture decision)
        message += "\n\nGates G1/G4: Always require human/CTO approval (never automated)"
        
        return (True, message)
    except ValueError as e:
        return (False, f"❌ Mode switch failed: {e}")


def set_override(task_id: str, mode_or_off: str) -> tuple[bool, str]:
    """Set or remove per-task execution mode override.
    
    Args:
        task_id: TASK_<id> identifier (e.g., 'TASK_DS_EO_021')
        mode_or_off: Target mode ('manual'/'automatic') or 'off' to remove override
        
    Returns:
        Tuple of (success: bool, message: str)
            - success=True → override set/removed with confirmation
            - success=False → invalid input, message contains error details
    """
    selector = create_selector()
    
    # Validate task_id format
    if not task_id.startswith('TASK_'):
        return (False, f"❌ Invalid task ID '{task_id}'. Must start with 'TASK_'")
    
    # Handle 'off' to remove override
    if mode_or_off.lower() == 'off':
        try:
            previous = selector.config.task_overrides.get(task_id)
            
            if previous is None:
                return (False, f"ℹ️  No override existed for {task_id}")
            
            # Remove the override
            del selector.config.task_overrides[task_id]
            
            return (True, f"✅ Removed per-task override for {task_id}. Task now uses global default mode.")
        except KeyError:
            return (False, f"ℹ️  No override existed for {task_id}")
    
    # Validate mode value
    if mode_or_off not in ('manual', 'automatic'):
        return (False, f"❌ Invalid mode '{mode_or_off}'. Must be one of: manual, automatic")
    
    try:
        previous, new_mode = selector.switch_task_mode(task_id, mode_or_off)
        
        if previous is None:
            message = f"✅ Set per-task override for {task_id}: {new_mode}"
        else:
            message = f"✅ Updated per-task override for {task_id}: {previous} → {new_mode}"
        
        return (True, message)
    except ValueError as e:
        return (False, f"❌ Failed to set override: {e}")


def format_status() -> str:
    """Format human-readable status string for /eo mode status command.
    
    Returns:
        Multi-line status string showing current mode and overrides
    """
    selector = create_selector()
    current_mode = selector.get_current_mode()
    task_overrides = selector.config.task_overrides
    
    lines = [f"Execution Mode: {current_mode}"]
    lines.append("")
    
    if task_overrides:
        lines.append("Per-task overrides:")
        for task_id, mode in sorted(task_overrides.items()):
            lines.append(f"  {task_id} → {mode}")
        lines.append("")
        lines.append("(no overrides for other tasks → use global default)")
    else:
        lines.append("Per-task overrides: (none)")
    
    # Add architecture note about G1/G4 gates (per D4)
    lines.append("")
    lines.append("Gates G1/G4: Always require human/CTO approval (never automated)")
    
    return "\n".join(lines)
