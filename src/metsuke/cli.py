# -*- coding: utf-8 -*-
"""CLI command implementations for Metsuke."""

import click
import sys
import os
from pathlib import Path
from typing import Optional, List
import importlib.util
import toml
import yaml
# import yaml - Using ruamel.yaml for loading in update-plan if needed
from ruamel.yaml import YAML
import logging
import io

# Import core functions and exceptions
from .core import find_plan_files, load_plans, manage_focus, save_plan, PLANS_DIR_NAME, PLAN_FILE_PATTERN, DEFAULT_PLAN_FILENAME
from .exceptions import PlanLoadingError, PlanValidationError
from .models import Project, ProjectMeta, Task

# Need ValidationError for checking updated schema
from pydantic import ValidationError

# --- Module Level Templates --- 
# Define templates here so they can be accessed by multiple commands (init, update-plan)
DEFAULT_PLAN_FILENAME_FOR_TEMPLATE = "PROJECT_PLAN.yaml" # Use a distinct name to avoid conflict with core constant if imported
project_name_placeholder = "Your Project Name" # Placeholder for template
project_version_placeholder = "0.1.0" # Placeholder for template
collaboration_guide_template = f"""\
# {DEFAULT_PLAN_FILENAME_FOR_TEMPLATE} - {project_name_placeholder} Project
# -------------------- Collaboration Usage --------------------
# This file serves as the primary planning and tracking document for {project_name_placeholder}.
# AI assistants should primarily interact with the plan file where 'focus: true' is set.
#
# As the AI assistant, I will adhere to the following process for planning:
#   1. Engage in an initial discussion phase (e.g., INNOVATE mode) to fully understand project goals, context, and constraints before modifying this plan.
#   2. Summarize key discussion points, decisions, and rationale in a designated document (e.g., `docs/discussion_log.md`) for transparency and future reference.
#   3. Propose an initial, high-level task breakdown in this file (PLAN mode).
#   4. Based on user feedback, iteratively refine and decompose tasks into more specific, granular, and actionable steps until the plan is sufficiently detailed for execution.
#   5. Ensure each task has a clear description, status, priority, and dependencies correctly mapped.
#   6. Maintain and update the status of each task (pending, in_progress, Done).
#   7. Automatically record the 'completion_date' when a task is marked 'Done'.
#   8. Refer to these tasks when discussing development steps with you.
#   9. Request explicit confirmation (e.g., "ENTER EXECUTE MODE" or similar) before starting the implementation of any task described herein. Upon receiving confirmation, immediately update the task status to `in_progress` before proceeding.
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
#   completion_date: ISO 8601 datetime string or null (Automatically set when status becomes 'Done').
#   context: Optional string containing project context/notes (displays in Help '?').
"""

context_template = f"""\
## {project_name_placeholder} (Replace Me)

### Goal
Briefly describe the main goal of this project.

### Core Components
*   List the main parts or modules of the project.
*   Component B
*   ...

### Notes
Any other relevant context for the AI assistant.
"""

tasks_template = [
    {'id': 1, 'title': 'Set up initial project structure', 'description': '''**Plan:**
1. Define directory layout (src, tests, docs, etc.).
2. Initialize version control (e.g., git init).
3. Create basic config files (.gitignore, pyproject.toml, etc.).''', 'status': 'pending', 'priority': 'high', 'dependencies': [], 'completion_date': None},
    {'id': 2, 'title': 'Define core data models/schemas', 'description': '''**Plan:**
1. Identify key data structures.
2. Implement using Pydantic, dataclasses, or similar.''', 'status': 'pending', 'priority': 'medium', 'dependencies': [1], 'completion_date': None},
    {'id': 3, 'title': 'Implement basic feature X', 'description': '''**Plan:**
1. Define inputs and outputs.
2. Implement core logic.
3. Add basic error handling.''', 'status': 'pending', 'priority': 'medium', 'dependencies': [2], 'completion_date': None},
    {'id': 4, 'title': 'Set up testing framework', 'description': '''**Plan:**
1. Choose testing framework (e.g., pytest).
2. Add framework to dev dependencies.
3. Create initial test file(s).''', 'status': 'pending', 'priority': 'low', 'dependencies': [1], 'completion_date': None},
    {'id': 5, 'title': 'Set up CI/CD pipeline', 'description': '''**Plan:**
1. Choose CI/CD platform (e.g., GitHub Actions).
2. Create basic workflow (lint, test).
3. Configure triggers.''', 'status': 'pending', 'priority': 'low', 'dependencies': [1, 4], 'completion_date': None},
]

# Default plan filename
# PLAN_FILENAME = "PROJECT_PLAN.yaml"

# Helper function to get focus plan
def _get_focus_plan(plan_path_option: Optional[Path]):
    plan_files = find_plan_files(Path.cwd(), plan_path_option)
    if not plan_files:
        click.echo("Error: No plan files found.", err=True)
        return None, None

    loaded_plans = load_plans(plan_files)
    updated_plans, focus_path = manage_focus(loaded_plans)

    if focus_path is None or focus_path not in updated_plans or updated_plans[focus_path] is None:
        click.echo("Error: Could not determine or load the focus plan.", err=True)
        valid_plans = {p: plan for p, plan in updated_plans.items() if plan}
        if valid_plans:
             first_valid_path = sorted(valid_plans.keys())[0]
             click.echo(f"Info: Displaying first valid plan found: {first_valid_path.name}", err=True)
             return valid_plans[first_valid_path], first_valid_path
        return None, None

    return updated_plans[focus_path], focus_path


@click.command("show-info")
@click.pass_context
def show_info(ctx):
    """Show project information from the focus plan file."""
    plan_path_option = ctx.parent.params.get('plan_path_option')
    try:
        project_data, focus_path = _get_focus_plan(plan_path_option)
        if not project_data or not focus_path:
            sys.exit(1)

        click.echo(f"--- Focus Plan: {focus_path.name} ---")
        click.echo(f"Project Name: {project_data.project.name}")
        click.echo(f"Version: {project_data.project.version}")
        if project_data.project.license:
             click.echo(f"License: {project_data.project.license}")
        click.echo("\n-- Context --")
        click.echo(project_data.context or "No context provided.")

    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        logging.exception("Unexpected error in show-info")
        sys.exit(1)


@click.command("list-tasks")
@click.pass_context
def list_tasks(ctx):
    """List tasks from the focus plan file."""
    plan_path_option = ctx.parent.params.get('plan_path_option')
    try:
        project_data, focus_path = _get_focus_plan(plan_path_option)
        if not project_data or not focus_path:
            sys.exit(1)

        click.echo(f"--- Tasks for Focus Plan: {focus_path.name} ---")
        if not project_data.tasks:
            click.echo("No tasks found in the plan.")
            return

        id_width = 4
        status_width = 15
        click_status_width = 25

        header = f"{'ID':<{id_width}} {'Status':<{status_width}} {'Title'}"
        click.echo(header)
        click.echo("-" * id_width + " " + "-" * status_width + " " + "-" * (len(header) - id_width - status_width - 2))

        for task in project_data.tasks:
            status_color = {
                "Done": "green",
                "in_progress": "yellow",
                "pending": "blue",
                "blocked": "red",
            }.get(task.status, "white")
            styled_status = click.style(task.status, fg=status_color)
            status_padding = " " * (click_status_width - len(task.status))
            click.echo(f"{task.id:<{id_width}} {styled_status}{status_padding} {task.title}")

    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        logging.exception("Unexpected error in list-tasks")
        sys.exit(1)


@click.command("init")
@click.option('--mode', type=click.Choice(['single', 'multi']), default='single', help='Create a single root plan or a multi-plan structure in plans/.')
def init(mode):
    """Initialize a new project plan file (PROJECT_PLAN.yaml or plans/PROJECT_PLAN_main.yaml).

    Creates a plan file with a default structure, example tasks, project context
    template, and collaboration guidelines for AI assistants.

    It attempts to detect project name/version from pyproject.toml but uses
    placeholders in the generated template. The file will be populated with
    initial task examples.

    Use `--mode multi` to create a `plans/` directory and place the initial
    plan file inside as `PROJECT_PLAN_main.yaml`, suitable for managing multiple
    sub-project plans. By default (`--mode single`), it creates `PROJECT_PLAN.yaml`
    in the current directory.
    """
    # Define plan filename constants locally for init command
    DEFAULT_PLAN_FILENAME = "PROJECT_PLAN.yaml"
    PLANS_DIR_NAME = "plans"
    DEFAULT_MULTI_FILENAME = f"PROJECT_PLAN_main.yaml"

    # Ensure target_filename is always a Path object
    target_filename = Path(DEFAULT_PLAN_FILENAME) if mode == 'single' else Path(PLANS_DIR_NAME) / DEFAULT_MULTI_FILENAME
    target_dir = Path(PLANS_DIR_NAME) if mode == 'multi' else Path.cwd()

    if target_filename.exists():
        click.echo(f"Error: {target_filename} already exists.", err=True)
        sys.exit(1)

    # Create plans directory if needed
    if mode == 'multi':
        try:
            target_dir.mkdir(exist_ok=True)
            click.echo(f"Ensured directory exists: {target_dir}")
        except OSError as e:
            click.echo(f"Error creating directory {target_dir}: {e}", err=True)
            sys.exit(1)

    # --- Extract Metadata (but use placeholders for template) --- 
    pyproject_path = "pyproject.toml"

    try:
        if os.path.exists(pyproject_path):
            config = toml.load(pyproject_path)
            project_section = config.get('project', {})
            # Read detected values but don't overwrite template placeholders
            detected_name = project_section.get('name')
            detected_version = project_section.get('version')
            if detected_name and detected_version:
                 click.echo(f"Detected project info in {pyproject_path}: {detected_name} v{detected_version}. Using placeholders in template.")
            elif detected_name:
                 click.echo(f"Detected project name '{detected_name}' in {pyproject_path}. Using placeholders in template.")
            else:
                 click.echo(f"No project name/version found in {pyproject_path}. Using default placeholders.")
        else:
            click.echo(f"No {pyproject_path} found, using default placeholders.")
    except toml.TomlDecodeError as e:
        click.echo(f"Warning: Could not parse {pyproject_path}: {e}", err=True)
    except Exception as e:
        click.echo(f"Warning: Unexpected error reading {pyproject_path}: {e}", err=True)

    # --- Construct YAML Content --- 
    project_dict = {
        'project': {'name': project_name_placeholder, 'version': project_version_placeholder},
        'context': context_template,
        'tasks': tasks_template,
        'focus': True # Set focus to true for the initial plan
    }

    try:
        # Use safe_dump and disable aliases for cleaner output
        yaml_content = yaml.safe_dump(
            project_dict, 
            default_flow_style=False, 
            sort_keys=False, 
            allow_unicode=True, 
            indent=2
        )
    except Exception as e:
         click.echo(f"Error generating YAML content: {e}", err=True)
         sys.exit(1)

    # --- Write File --- 
    try:
        with open(target_filename, "w", encoding="utf-8") as f:
            f.write(collaboration_guide_template)
            f.write("\n")
            f.write(yaml_content)
        click.echo(f"Successfully created {target_filename}!")
    except IOError as e:
        click.echo(f"Error writing file {target_filename}: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred during file writing: {e}", err=True)
        sys.exit(1)


@click.command("add-plan")
@click.argument("subproject_name", type=str)
@click.pass_context
def add_plan(ctx, subproject_name):
    """Create a new plan file in plans/ and set it as focus."""
    base_dir = Path.cwd()
    plans_dir = base_dir / PLANS_DIR_NAME

    # 1. Environment Check
    if not plans_dir.is_dir():
        click.echo(f"Error: Directory '{PLANS_DIR_NAME}' not found.", err=True)
        click.echo(f"This command requires multi-plan mode. Run 'metsuke init --mode multi' first?", err=True)
        sys.exit(1)

    # 2. Filename Generation and Conflict Check
    # Basic sanitization (replace spaces, convert to lower) - might need more robust slugify
    safe_subproject_name = subproject_name.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
    new_plan_filename = f"PROJECT_PLAN_{safe_subproject_name}.yaml"
    new_plan_path = plans_dir / new_plan_filename

    if new_plan_path.exists():
        click.echo(f"Error: Plan file '{new_plan_path}' already exists.", err=True)
        sys.exit(1)

    # 3. Find and Unfocus Old Plan
    old_focus_path_str = "None"
    try:
        # We only care about files within plans_dir for focus management here
        plan_files_in_dir = find_plan_files(base_dir, plans_dir) # Force search in plans dir
        if not plan_files_in_dir:
             click.echo(f"Warning: No existing plan files found in '{PLANS_DIR_NAME}'. Creating first plan.", err=True)
             old_focus_path = None
        else:
            loaded_plans = load_plans(plan_files_in_dir)
            # Manage focus ensures only one focus exists, returns the path
            updated_plans, old_focus_path = manage_focus(loaded_plans)

            if old_focus_path and old_focus_path in updated_plans and updated_plans[old_focus_path]:
                old_plan = updated_plans[old_focus_path]
                if old_plan.focus: # Should be true if manage_focus worked
                    click.echo(f"Removing focus from previous plan: {old_focus_path.relative_to(base_dir)}")
                    old_plan.focus = False
                    if not save_plan(old_plan, old_focus_path):
                        click.echo(f"Warning: Failed to save focus change for {old_focus_path}. Proceeding cautiously.", err=True)
                        # Continue, but the state might be slightly off until next focus management
                    old_focus_path_str = str(old_focus_path.relative_to(base_dir))
            else:
                 click.echo(f"Warning: Could not determine or load the previous focus plan in '{PLANS_DIR_NAME}'.", err=True)
                 old_focus_path = None # Treat as if no previous focus

    except Exception as e:
        click.echo(f"Error during focus management: {e}. Aborting.", err=True)
        logging.exception("Error managing focus in add-plan")
        sys.exit(1)

    # 4. Create New Plan Content
    click.echo(f"Creating new plan file: {new_plan_path.relative_to(base_dir)}")
    new_project = Project(
        project=ProjectMeta(
            name=subproject_name, # Use the provided name
            version="0.1.0" # Default version
        ),
        context=f"## Plan for {subproject_name}\n\nDescribe the goals and context for this sub-project here.",
        tasks=[], # Start with empty task list
        focus=True # Set new plan as focus
    )

    # 5. Save New Plan
    if not save_plan(new_project, new_plan_path):
        click.echo(f"Error: Failed to save new plan file to {new_plan_path}.", err=True)
        # Attempt to revert focus on old plan? Difficult state to recover.
        # Best to exit with error, user needs to manually fix YAML files.
        if old_focus_path:
            click.echo(f"Critical Error: New plan save failed. Focus might be inconsistent. Please manually check {old_focus_path} and {new_plan_path}", err=True)
        sys.exit(1)

    # 6. Feedback
    click.echo(f"Successfully created and focused plan: {new_plan_path.relative_to(base_dir)}")
    if old_focus_path:
        click.echo(f"Previous focus was removed from: {old_focus_path_str}")


@click.command("update-plan")
@click.argument("path_spec", type=click.Path(exists=False, path_type=Path), required=False, default=None)
def update_plan(path_spec: Optional[Path]):
    """Check and update plan file(s) to the latest schema format."""
    click.echo("Checking and updating plan file schema...")

    # Use ruamel.yaml for round-trip loading/saving to preserve comments/structure
    yaml_rt = YAML(typ='rt') # rt = round-trip
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    yaml_rt.preserve_quotes = True

    # 1. Find files based on path_spec or default rules
    files_to_check = find_plan_files(Path.cwd(), path_spec)

    if not files_to_check:
        click.echo("Error: No plan files found to update based on the provided path or discovery.", err=True)
        sys.exit(1)

    # Determine mode *after* finding files
    is_multi_mode = len(files_to_check) > 1

    click.echo(f"Found {len(files_to_check)} plan file(s) to check:")
    for f_path in files_to_check:
        try:
            click.echo(f" - {f_path.relative_to(Path.cwd())}")
        except ValueError:
            click.echo(f" - {f_path}") # Fallback for absolute paths outside cwd

    # 2. Loop through files
    click.echo("\nProcessing files...")
    updated_count = 0
    checked_count = 0
    validation_error_count = 0
    error_count = 0

    for f_path in files_to_check:
        checked_count += 1
        was_modified = False
        relative_path_str = str(f_path.relative_to(Path.cwd()) if f_path.is_relative_to(Path.cwd()) else f_path)
        try:
            # 3. Load raw YAML data using ruamel.yaml
            with open(f_path, 'r', encoding='utf-8') as fp:
                # Read header lines first
                header_lines: List[str] = []
                non_header_lines: List[str] = []
                is_header = True
                for line in fp:
                    stripped_line = line.strip()
                    if is_header and stripped_line.startswith('#'):
                        header_lines.append(line)
                    elif is_header and stripped_line == '' and not header_lines:
                        continue # Skip leading blanks
                    else:
                        is_header = False
                        non_header_lines.append(line)

                # Join the non-header part back for ruamel to load
                yaml_data_str = "".join(non_header_lines)
                data = yaml_rt.load(yaml_data_str)
            
            if not isinstance(data, dict):
                click.echo(f"Skipping {relative_path_str}: Invalid format (expected root dictionary).", err=True)
                validation_error_count += 1 # Treat format errors as validation errors
                error_count += 1
                continue

            # --- Check Header Comment --- 
            current_header_str = "".join(header_lines)
            # Simple comparison, might need refinement
            if current_header_str.strip() != collaboration_guide_template.strip(): 
                 click.echo(f"  - Updating header comment in {relative_path_str}")
                 # Split template ensuring newlines are kept for writelines
                 header_lines = [line + '\n' for line in collaboration_guide_template.splitlines()]
                 was_modified = True

            # 4. Check for top-level 'focus' key
            if 'focus' not in data:
                click.echo(f"  - Adding missing 'focus' key to {relative_path_str}")
                # Default to True for single files, False for multi-mode
                default_focus = True if not is_multi_mode else False
                # Add comment explaining the field
                data.insert(0, 'focus', default_focus, comment="Indicates the currently active plan for AI interaction (only one file should be true).")
                was_modified = True

            # 5. Iterate through tasks, check for 'completion_date'
            if 'tasks' in data and isinstance(data['tasks'], list):
                for task in data['tasks']:
                    if isinstance(task, dict) and 'completion_date' not in task:
                        click.echo(f"  - Adding missing 'completion_date' to Task ID {task.get('id', 'N/A')} in {relative_path_str}")
                        task['completion_date'] = None
                        was_modified = True
            
            if was_modified:
                click.echo(f"Modifications made to {relative_path_str}. Validating and attempting save...")
                # 6. Attempt to validate the *modified* dict with Project.model_validate
                try:
                    validated_project = Project.model_validate(data)
                    # 7. If valid, save back using yaml_rt.dump()
                    try:
                        project_dict_to_save = validated_project.model_dump(mode='python')
                        yaml_string_buffer = io.StringIO()
                        yaml_rt.dump(project_dict_to_save, yaml_string_buffer) # Dump validated data
                        yaml_content = yaml_string_buffer.getvalue()

                        with open(f_path, 'w', encoding='utf-8') as fp:
                            fp.writelines(header_lines)
                            fp.write(yaml_content)
                        click.echo(f"  Successfully validated and saved {relative_path_str}")
                        updated_count += 1
                    except IOError as io_err:
                        click.echo(f"  Error saving file {relative_path_str}: {io_err}", err=True)
                        error_count += 1
                except ValidationError as val_err:
                    click.echo(f"  Validation failed for {relative_path_str} after modifications: {val_err}", err=True)
                    click.echo(f"  File was NOT saved.")
                    validation_error_count += 1
                    error_count += 1 # Also count as general error
            else:
                click.echo(f"{relative_path_str} is already up-to-date.")

        except FileNotFoundError:
            click.echo(f"Error: File not found during processing: {relative_path_str}", err=True)
            error_count += 1
        except Exception as e: # Catch ruamel.yaml errors or others
            click.echo(f"Error processing file {relative_path_str}: {e}", err=True)
            logging.exception(f"Error details for {relative_path_str}")
            error_count += 1

    click.echo("\n--- Update Summary ---")
    click.echo(f"Checked: {checked_count} file(s)")
    click.echo(f"Successfully Updated & Saved: {updated_count} file(s)")
    if validation_error_count > 0:
        click.echo(f"Validation Errors (not saved): {validation_error_count} file(s)", err=True)
    click.echo(f"Errors: {error_count} file(s)")


@click.command("tui")
@click.pass_context
def run_tui(ctx):
    """Launch the interactive Terminal User Interface (TUI) to view and manage plans.

    Requires optional dependencies. Install with: pip install "metsuke[tui]"
    """
    plan_path_option = ctx.parent.params.get('plan_path_option')

    plan_files = find_plan_files(Path.cwd(), plan_path_option)

    if not plan_files:
        click.echo("Error: No plan files found to launch TUI.", err=True)
        sys.exit(1)

    click.echo(f"Found {len(plan_files)} plan file(s):")
    for pf in plan_files:
        click.echo(f" - {pf.relative_to(Path.cwd())}")

    try:
        from .tui.app import TaskViewer
    except ImportError as e:
        click.echo(f"Error importing TUI components: {e}", err=True)
        click.echo("Ensure Metsuke is installed correctly.", err=True)
        logging.exception("Error importing TUI")
        sys.exit(1)

    try:
        app = TaskViewer(plan_files=plan_files)
        app.run()
    except Exception as e:
        click.echo(f"Error running TUI: {e}", err=True)
        logging.exception("Error running TUI")
        sys.exit(1) 