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
# Import the template from core
from .core import collaboration_guide_template

# Need ValidationError for checking updated schema
from pydantic import ValidationError

# --- Module Level Templates --- 
# Define templates here so they can be accessed by multiple commands (init, update-plan)
# DEFAULT_PLAN_FILENAME_FOR_TEMPLATE = "PROJECT_PLAN.yaml" # Removed
project_name_placeholder = "Your Project Name" # KEEP THIS
project_version_placeholder = "0.1.0" # KEEP THIS
# collaboration_guide_template = f"""...""" # Removed

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
""" # KEEP THIS

tasks_template = [
    {'id': 1, 'title': 'Set up initial project structure', 'description': '''**Plan:**
1. Define directory layout (src, tests, docs, etc.).
2. Initialize version control (e.g., git init).
3. Create basic config files (.gitignore, pyproject.toml, etc.).''', 'status': 'pending', 'priority': 'high', 'dependencies': []},
    {'id': 2, 'title': 'Define core data models/schemas', 'description': '''**Plan:**
1. Identify key data structures.
2. Implement using Pydantic, dataclasses, or similar.''', 'status': 'pending', 'priority': 'medium', 'dependencies': [1]},
    {'id': 3, 'title': 'Implement basic feature X', 'description': '''**Plan:**
1. Define inputs and outputs.
2. Implement core logic.
3. Add basic error handling.''', 'status': 'pending', 'priority': 'medium', 'dependencies': [2]},
    {'id': 4, 'title': 'Set up testing framework', 'description': '''**Plan:**
1. Choose testing framework (e.g., pytest).
2. Add framework to dev dependencies.
3. Create initial test file(s).''', 'status': 'pending', 'priority': 'low', 'dependencies': [1]},
    {'id': 5, 'title': 'Set up CI/CD pipeline', 'description': '''**Plan:**
1. Choose CI/CD platform (e.g., GitHub Actions).
2. Create basic workflow (lint, test).
3. Configure triggers.''', 'status': 'pending', 'priority': 'low', 'dependencies': [1, 4]},
] # KEEP THIS

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
    # --- ADD COMMENT: Template Dependency ---
    # NOTE: This command generates a new plan file based on standard templates
    # defined in this module (or imported from core.py). This includes the
    # standard collaboration usage comment block (`collaboration_guide_template`).
    # If the standard comment template is updated (e.g., in PROJECT_PLAN.yaml or core.py),
    # this command's output MUST be updated accordingly to maintain consistency.
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
    """Create a new plan file in plans/ with default templates."""
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

    # 4. Create New Plan Content
    click.echo(f"Creating new plan file: {new_plan_path.relative_to(base_dir)}")
    new_project = Project(
        project=ProjectMeta(
            name=subproject_name, # Use the provided name
            version="0.1.0" # Default version
        ),
        context=context_template, # Use the module-level template
        tasks=tasks_template, # Use the module-level template
        focus=False # New plans should typically not be focus initially
    )

    # --- 5. Save New Plan (Revised to write header first) ---
    try:
        # Serialize the Pydantic model to a dictionary
        project_dict = new_project.model_dump(mode='python')
        # Generate YAML content string from the dictionary
        yaml_content = yaml.safe_dump(
            project_dict,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            indent=2
        )

        # Write the header and YAML content manually
        with open(new_plan_path, "w", encoding="utf-8") as f:
            f.write(collaboration_guide_template)
            f.write("\n") # Ensure a newline after the template
            f.write(yaml_content)
            
        click.echo(f"Successfully created plan: {new_plan_path.relative_to(base_dir)} (focus remains unchanged)")
    except Exception as e:
        click.echo(f"Error creating or writing plan file {new_plan_path}: {e}", err=True)
        logging.exception("Error in add-plan save operation")
        sys.exit(1)


@click.command("update-plan")
@click.argument("path_spec", type=click.Path(exists=False, path_type=Path), required=False, default=None)
def update_plan(path_spec: Optional[Path]):
    # --- ADD COMMENT: Scope and Potential Enhancement ---
    # NOTE: This command currently focuses on migrating the *data structure* of existing
    # plan files to the latest schema (e.g., ensuring 'focus' and 'completion_date' fields exist).
    # IDEALLY, it should ALSO update the header comment block (collaboration usage guidelines)
    # in existing plan files to match the latest standard template (`collaboration_guide_template`)
    # to ensure consistency across all project plans.
    # TODO: Consider enhancing this command to include header comment updates in the future.
    """Update existing plan file(s) to the latest schema.

    Check and update plan file(s) to the latest schema format.
    """
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

            # --- Clean up removed fields (e.g., completion_date) --- # Add this block
            if 'tasks' in data and isinstance(data['tasks'], list):
                for task_index, task in enumerate(data['tasks']): # Use enumerate for better logging if needed
                    if isinstance(task, dict) and 'completion_date' in task:
                        click.echo(f"  - Removing deprecated 'completion_date' from Task ID {task.get('id', f'at index {task_index}')} in {relative_path_str}")
                        del task['completion_date']
                        was_modified = True
            # --- End cleanup ---
            
            if was_modified:
                click.echo(f"Modifications made to {relative_path_str}. Validating and attempting save...")
                # 6. Attempt to validate the *modified* dict with Project.model_validate
                try:
                    validated_project = Project.model_validate(data)
                    # 7. If valid, save back using yaml_rt.dump()
                    try:
                        # project_dict_to_save = validated_project.model_dump(mode='python') # REMOVE THIS LINE
                        yaml_string_buffer = io.StringIO()
                        # yaml_rt.dump(project_dict_to_save, yaml_string_buffer) # Modify this line
                        yaml_rt.dump(data, yaml_string_buffer) # Dump the modified 'data' object directly
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