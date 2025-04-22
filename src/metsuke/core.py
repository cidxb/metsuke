# -*- coding: utf-8 -*-
"""Core logic for Metsuke: loading, parsing, validating plans."""

import yaml
from ruamel.yaml import YAML # Import ruamel.yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple # Add new types
import logging # Add logging
import io

from pydantic import ValidationError

from .models import Project
from .exceptions import PlanLoadingError, PlanValidationError

# Default plan filename and pattern
DEFAULT_PLAN_FILENAME = "PROJECT_PLAN.yaml"
PLAN_FILE_PATTERN = "PROJECT_PLAN_*.yaml"
PLANS_DIR_NAME = "plans"

# Logger for core functions
logger = logging.getLogger(__name__)


def find_plan_files(base_dir: Path, explicit_path: Optional[Path]) -> List[Path]:
    """Finds project plan files based on explicit path or discovery rules."""
    if explicit_path:
        if explicit_path.is_file():
            logger.info(f"Using explicit plan file: {explicit_path}")
            return [explicit_path]
        elif explicit_path.is_dir():
            logger.info(f"Searching for plan files in explicit directory: {explicit_path}")
            plan_files = sorted(list(explicit_path.glob(PLAN_FILE_PATTERN)))
            if not plan_files:
                 logger.warning(f"No '{PLAN_FILE_PATTERN}' files found in directory: {explicit_path}")
            return plan_files
        else:
            logger.warning(f"Explicit path does not exist or is not a file/directory: {explicit_path}")
            return []

    # No explicit path, try discovery
    plans_dir = base_dir / PLANS_DIR_NAME
    if plans_dir.is_dir():
        logger.info(f"Searching for plan files in default directory: {plans_dir}")
        plan_files = sorted(list(plans_dir.glob(PLAN_FILE_PATTERN)))
        if plan_files:
            logger.info(f"Found {len(plan_files)} plan(s) in {plans_dir}.")
            return plan_files
        else:
             logger.info(f"No '{PLAN_FILE_PATTERN}' files found in {plans_dir}.")

    # Fallback to default root file
    default_file = base_dir / DEFAULT_PLAN_FILENAME
    if default_file.is_file():
        logger.info(f"Using default plan file in root directory: {default_file}")
        return [default_file]

    logger.warning(f"No plan files found via discovery (checked {plans_dir} and {default_file}).")
    return []


def load_plans(plan_files: List[Path]) -> Dict[Path, Optional[Project]]:
    """Loads and validates multiple plan files."""
    loaded_plans: Dict[Path, Optional[Project]] = {}
    for filepath in plan_files:
        if not filepath.is_file():
            logger.error(f"Plan file vanished before loading: {filepath}")
            loaded_plans[filepath] = None # Mark as error
            continue
        try:
            logger.debug(f"Attempting to load plan: {filepath}")
            with open(filepath, "r", encoding="utf-8") as f:
                # Using standard yaml loader here is fine, ruamel is for saving
                data: Dict[Any, Any] = yaml.safe_load(f)
                if data is None:
                    raise PlanLoadingError(f"Plan file is empty: {filepath.resolve()}")
            project_data = Project.model_validate(data)
            loaded_plans[filepath] = project_data
            logger.debug(f"Successfully loaded and validated: {filepath}")
        except (FileNotFoundError, PlanLoadingError) as e:
            logger.error(f"Error loading plan file {filepath}: {e}")
            loaded_plans[filepath] = None
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {filepath}: {e}")
            loaded_plans[filepath] = None
        except ValidationError as e:
            # Log validation errors clearly
            error_details = f"Plan validation failed for {filepath.resolve()}:\n"
            for error in e.errors():
                loc = ".".join(map(str, error['loc']))
                error_details += f"  - Field '{loc}': {error['msg']} (value: {error.get('input')})\n"
            logger.error(error_details.strip()) # Log detailed error
            loaded_plans[filepath] = None # Mark as error
        except Exception as e:
            logger.error(f"Unexpected error reading or validating file {filepath}: {e}", exc_info=True)
            loaded_plans[filepath] = None
    return loaded_plans


def save_plan(project: Project, filepath: Path) -> bool:
    """Saves a Project object back to a YAML file, preserving structure."""
    try:
        # --- Preserve Header Comments --- 
        header_lines: List[str] = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f_read:
                for line in f_read:
                    stripped_line = line.strip()
                    if stripped_line.startswith('#'):
                        header_lines.append(line) # Keep original line ending
                    elif stripped_line == '' and not header_lines: # Skip leading blank lines
                        continue
                    else:
                        break # Stop at first non-comment/non-empty line
        except FileNotFoundError:
            logger.debug(f"File {filepath} not found, creating new file (no header to preserve).")
            pass # File doesn't exist yet, no header to preserve
        except Exception as e:
            logger.warning(f"Could not read header from {filepath}: {e}") # Log warning but proceed

        # Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Use ruamel.yaml for round-trip safety
        yaml_saver = YAML(typ='safe', pure=True)
        yaml_saver.indent(mapping=2, sequence=4, offset=2)
        yaml_saver.preserve_quotes = True
        yaml_saver.width = 1000 # Prevent line wrapping

        # Convert Pydantic model to dict, handling datetime
        # Use model_dump for Pydantic v2
        project_dict = project.model_dump(mode='python') # mode='python' often helps with types like datetime

        # Dump YAML data to an in-memory buffer
        yaml_string_buffer = io.StringIO()
        yaml_saver.dump(project_dict, yaml_string_buffer)
        yaml_content = yaml_string_buffer.getvalue()

        logger.debug(f"Attempting to save plan to: {filepath}")
        # Write header (if any) and then the YAML content
        with open(filepath, 'w', encoding='utf-8') as f_write:
            f_write.writelines(header_lines)
            # Add a newline between header and YAML if header exists
            # if header_lines and not yaml_content.startswith('---'): # Avoid double --- if ruamel adds it
            #     f_write.write("\n")
            f_write.write(yaml_content)

        logger.info(f"Successfully saved plan: {filepath}")
        return True
    except IOError as e:
        logger.error(f"Error writing plan file {filepath}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving plan file {filepath}: {e}", exc_info=True)
        return False


def manage_focus(
    loaded_plans: Dict[Path, Optional[Project]],
    new_focus_target: Optional[Path] = None
) -> Tuple[Dict[Path, Optional[Project]], Optional[Path]]:
    """Ensures exactly one plan has focus=true, updating files if necessary.

    Args:
        loaded_plans: Dictionary mapping file paths to loaded Project objects (or None if load failed).
        new_focus_target: Optional path to the plan that should be focused.
                        If None, automatically manages focus (ensure one, default to first).
                        If provided, sets this plan to focus and unfocuses others.

    Returns:
        A tuple containing:
        - The updated loaded_plans dictionary (potentially with modified focus flags).
        - The Path of the plan that has focus after management, or None.
    """
    valid_plans = {path: plan for path, plan in loaded_plans.items() if plan is not None}
    if not valid_plans:
        logger.warning("No valid plans loaded, cannot manage focus.")
        return loaded_plans, None

    plans_to_save: List[Tuple[Project, Path]] = []
    focus_path: Optional[Path] = None # Initialize focus_path

    if new_focus_target:
        if new_focus_target not in valid_plans:
            logger.warning(f"Target focus path {new_focus_target} is not a valid loaded plan. Ignoring target.")
            # Fall back to default behavior if target is invalid
            new_focus_target = None # Reset target so the 'else' block runs
        else:
            logger.info(f"Explicitly setting focus to: {new_focus_target}")
            focus_path = new_focus_target
            for path, plan in valid_plans.items():
                should_be_focused = (path == new_focus_target)
                if plan.focus != should_be_focused:
                    plan.focus = should_be_focused
                    plans_to_save.append((plan, path))
                    logger.debug(f"Marking {path} for save with focus={should_be_focused}")

    # Only run auto-management if no valid target was provided (or target was invalid)
    if not focus_path: # This covers new_focus_target being None or invalid
        focused_plans = {path: plan for path, plan in valid_plans.items() if plan.focus}

        if len(focused_plans) == 0:
            logger.warning("No plan has focus=true. Setting focus on the first valid plan.")
            first_path = sorted(valid_plans.keys())[0]
            focus_path = first_path
            valid_plans[first_path].focus = True
            plans_to_save.append((valid_plans[first_path], first_path))
        elif len(focused_plans) == 1:
            focus_path = list(focused_plans.keys())[0]
            logger.info(f"Confirmed single focus plan: {focus_path}")
        else: # More than one focus
            logger.warning(f"Multiple plans have focus=true ({len(focused_plans)} found). Fixing...")
            sorted_focused_paths = sorted(focused_plans.keys())
            focus_path = sorted_focused_paths[0]
            logger.info(f"Keeping focus on: {focus_path}")
            for i, path in enumerate(sorted_focused_paths):
                if i > 0:
                    logger.warning(f"Removing focus from: {path}")
                    focused_plans[path].focus = False
                    plans_to_save.append((focused_plans[path], path))

    # Save any changes made (common to both branches)
    if plans_to_save:
        logger.info(f"Saving focus changes for {len(plans_to_save)} plan(s).")
        for plan, path in plans_to_save:
            if not save_plan(plan, path):
                 logger.error(f"Failed to save focus change for {path}. Focus state might be inconsistent.")
    else:
        logger.info("No focus changes required saving.")


    # Update the main dictionary with potentially modified plan objects
    for path, plan in valid_plans.items():
         loaded_plans[path] = plan

    logger.info(f"Final focus path determined: {focus_path}")
    return loaded_plans, focus_path


# --- Old load_plan - Can be removed or kept for specific single-file loading ---
# If kept, it should probably use load_plans internally or be updated.
# For now, commenting out to avoid confusion and ensure new logic is used.

# def load_plan(filepath: Path = Path(DEFAULT_PLAN_FILENAME)) -> Project:
#     """Loads, parses, and validates the project plan YAML file. (OLD VERSION)"""
#     # ... (old implementation) ...
#     pass

# def load_plan(filepath: Path = Path("PROJECT_PLAN.yaml")) -> Project:
#     """Loads, parses, and validates the project plan YAML file.
#
#     Args:
#         filepath: The path to the project plan YAML file.
#                   Defaults to "PROJECT_PLAN.yaml" in the current directory.
#
#     Returns:
#         A validated Project object.
#
#     Raises:
#         PlanLoadingError: If the file cannot be found or parsed as YAML.
#         PlanValidationError: If the file content does not match the Project schema.
#     """
#     if not filepath.is_file():
#         raise PlanLoadingError(f"Plan file not found at: {filepath.resolve()}")
#
#     try:
#         with open(filepath, "r", encoding="utf-8") as f:
#             data: Dict[Any, Any] = yaml.safe_load(f)
#             if data is None: # Handle empty file case
#                 raise PlanLoadingError(f"Plan file is empty: {filepath.resolve()}")
#     except FileNotFoundError:
#         # Should be caught by is_file() check, but included for robustness
#         raise PlanLoadingError(f"Plan file not found at: {filepath.resolve()}")
#     except yaml.YAMLError as e:
#         raise PlanLoadingError(f"Error parsing YAML file: {filepath.resolve()}\n{e}")
#     except Exception as e: # Catch other potential file reading errors
#         raise PlanLoadingError(f"Error reading file: {filepath.resolve()}\n{e}")
#
#     try:
#         project_data = Project.model_validate(data)
#         return project_data
#     except ValidationError as e:
#         raise PlanValidationError(f"Plan validation failed for {filepath.resolve()}:\n{e}") 