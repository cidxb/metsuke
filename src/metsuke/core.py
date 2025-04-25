# -*- coding: utf-8 -*-
"""Core logic for Metsuke: loading, parsing, validating plans."""

import yaml
from ruamel.yaml import YAML # Import ruamel.yaml
# from ruamel.yaml.scalarstring import LiteralScalarString # Remove or comment out this import
from ruamel.yaml.scalarstring import FoldedScalarString # Add or ensure this import exists
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

# --- Template definitions moved from cli.py ---
DEFAULT_PLAN_FILENAME_FOR_TEMPLATE = "PROJECT_PLAN.yaml" 
project_name_placeholder = "Your Project Name" 
collaboration_guide_template = """\
# PROJECT_PLAN.yaml - Your Project Name Project
# -------------------- Collaboration Usage --------------------
# This file serves as the primary planning and tracking document for Your Project Name.
# AI assistants should primarily interact with the plan file where 'focus: true' is set.
#
# As the AI assistant, I will adhere to the following process for planning:
#   1. Engage in an initial discussion phase (e.g., INNOVATE mode) to fully understand project goals, context, and constraints before modifying this plan.
#   2. Summarize key discussion points, decisions, and rationale in a designated document (e.g., `docs/discussion_log.md`) for transparency and future reference.
#   3. Propose an initial, high-level task breakdown in this file (PLAN mode).
#   4. Based on user feedback, iteratively refine and decompose tasks into more specific, granular, and actionable steps until the plan is sufficiently detailed for execution.
#   5. Ensure each task has a clear description, status, priority, and dependencies correctly mapped.
#   6. Maintain and update the status of each task (pending, in_progress, Done).
#   7. Refer to these tasks when discussing development steps with you.
#   8. Request explicit confirmation (e.g., "ENTER EXECUTE MODE" or similar) before starting the implementation of any task described herein. Upon receiving confirmation, immediately update the task status to `in_progress` before proceeding.
#   9. **API Verification:** Before implementing any step involving external library APIs (e.g., Textual), I MUST first verify the correct API usage (imports, function signatures, event names, etc.) by consulting official documentation or performing web searches. Discrepancies between documentation and observed behavior should be noted.
#  10. Provide a specific test method or command (if applicable) after implementing a task, before marking it as Done.
# Please keep the context and task list updated to reflect the current project state.
# The 'focus: true' flag indicates the currently active plan for AI interaction.
# -------------------------------------------------------------
# Defines project metadata and tasks.
#
# Recommended values:
#   focus: [true, false] (Only one plan file should have true)
#   status: ['pending', 'in_progress', 'Done', 'blocked']
#   priority: ['low', 'medium', 'high']
#   dependencies: List of task IDs this task depends on. Empty list means no dependencies.
#   context: Optional string containing project context/notes (displays in Help '?').
"""
# --- End Template definitions ---

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
    yaml_loader = YAML(typ='rt') # Use ruamel.yaml round-trip loader
    for filepath in plan_files:
        if not filepath.is_file():
            logger.error(f"Plan file vanished before loading: {filepath}")
            loaded_plans[filepath] = None # Mark as error
            continue
        try:
            logger.debug(f"Attempting to load plan: {filepath}")
            with open(filepath, "r", encoding="utf-8") as f:
                # Using standard yaml loader here is fine, ruamel is for saving
                data = yaml_loader.load(f) # <-- Use ruamel loader
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
            logger.debug(f"File {filepath} not found, creating new file with default header.")
            # Assign default header lines when creating a new file
            # Split the template string into lines, ensuring each line ends with a newline
            header_lines = [line + '\n' for line in collaboration_guide_template.splitlines()]
            # Optionally, ensure there's a blank line separating header from YAML content
            if header_lines and not header_lines[-1].endswith('\n\n'):
                 header_lines.append('\n') 
        except Exception as e:
            logger.warning(f"Could not read header from {filepath}: {e}") # Log warning but proceed

        # Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Use ruamel.yaml for round-trip safety
        yaml_saver = YAML(typ='rt') # Change back to this
        # yaml_saver.default_style = '|' # Ensure this is removed
        yaml_saver.indent(mapping=2, sequence=4, offset=2)
        # yaml_saver.preserve_quotes = True # Ensure this remains commented/removed
        yaml_saver.width = 1000 # Prevent line wrapping

        # Convert Pydantic model to dict, handling datetime
        # Use model_dump for Pydantic v2
        project_dict = project.model_dump(mode='python') # mode='python' often helps with types like datetime

        # --- Convert specific fields to Folded style --- # Modify this block
        if isinstance(project_dict.get('context'), str) and project_dict['context']:
            # project_dict['context'] = LiteralScalarString(project_dict['context'])
            project_dict['context'] = FoldedScalarString(project_dict['context']) # Use Folded

        if isinstance(project_dict.get('tasks'), list):
            for task in project_dict['tasks']:
                if isinstance(task.get('description'), str) and task['description']:
                    # task['description'] = LiteralScalarString(task['description'])
                    task['description'] = FoldedScalarString(task['description']) # Use Folded
        # --- End conversion --- # Modify this block

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