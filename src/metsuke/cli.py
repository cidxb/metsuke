# -*- coding: utf-8 -*-
"""CLI command implementations for Metsuke."""

import click
import sys
import os
import pathlib
import importlib.util
import toml
import yaml

# Import core functions and exceptions
from .core import load_plan
from .exceptions import PlanLoadingError, PlanValidationError


# Default plan filename
PLAN_FILENAME = "PROJECT_PLAN.yaml"

@click.command("show-info")
def show_info():
    """Show project information from the plan file."""
    try:
        project_data = load_plan(pathlib.Path(PLAN_FILENAME))
        click.echo(f"Project Name: {project_data.project.name}")
        click.echo(f"Version: {project_data.project.version}")
        click.echo("\n-- Context --")
        click.echo(project_data.context)
    except PlanLoadingError as e:
        click.echo(f"Error loading plan: {e}", err=True)
        sys.exit(1)
    except PlanValidationError as e:
        click.echo(f"Error validating plan: {e}", err=True)
        sys.exit(1)
    except Exception as e: # Catch unexpected errors
        click.echo(f"An unexpected error occurred: {e}", err=True)
        sys.exit(1)


@click.command("list-tasks")
def list_tasks():
    """List tasks from the plan file."""
    try:
        project_data = load_plan(pathlib.Path(PLAN_FILENAME))
        if not project_data.tasks:
            click.echo("No tasks found in the plan.")
            return
        click.echo(f"{'ID':<4} {'Status':<15} {'Title'}")
        click.echo("-" * 4 + " " + "-" * 15 + " " + "-" * 40)
        for task in project_data.tasks:
            status_color = {
                "done": "green",
                "in_progress": "yellow",
                "pending": "blue",
                "blocked": "red",
            }.get(task.status.lower(), "white")
            styled_status = click.style(task.status, fg=status_color)
            click.echo(f"{task.id:<4} {styled_status:<25} {task.title}")
    except PlanLoadingError as e:
        click.echo(f"Error loading plan: {e}", err=True)
        sys.exit(1)
    except PlanValidationError as e:
        click.echo(f"Error validating plan: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        sys.exit(1)


@click.command("init")
def init():
    """Initialize a new PROJECT_PLAN.yaml in the current directory."""
    if os.path.exists(PLAN_FILENAME):
        click.echo(f"Error: {PLAN_FILENAME} already exists in this directory.", err=True)
        sys.exit(1)

    # --- Extract Metadata (but use placeholders for template) --- 
    project_name = "Your Project Name" # Placeholder for template
    project_version = "0.1.0" # Placeholder for template
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

    # --- Define Templates --- 
    collaboration_guide = f"""\
# {PLAN_FILENAME} - {project_name} Project
# -------------------- Collaboration Usage --------------------
# This file serves as the primary planning and tracking document for {project_name}.
# As the AI assistant, I will:
#   1. Analyze the project goals and context described herein.
#   2. Decompose high-level plans into specific, actionable tasks listed below.
#   3. Ensure tasks are broken down into fine-grained steps.
#   4. Write detailed descriptions for each task, including the specific plan/steps.
#   5. Maintain and update the status of each task (pending, in_progress, Done).
#   6. Refer to these tasks when discussing development steps with you.
#   7. Request confirmation before executing modifications based on these tasks.
#   8. Provide a specific test method or command (if applicable) after implementing a task, before marking it as Done.
# Please keep the context and task list updated to reflect the current project state.
# -------------------------------------------------------------
# Defines project metadata and tasks.
#
# Recommended values:
#   status: ['pending', 'in_progress', 'Done', 'blocked']
#   priority: ['low', 'medium', 'high']
#   dependencies: List of task IDs this task depends on. Empty list means no dependencies.
#   context: Optional string containing project context/notes (displays in Help '?').
"""

    context_template = f"""\
## {project_name} (Replace Me)

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
        {'id': 1, 'title': 'Set up initial project structure', 'description': '**Plan:**\n1. Define directory layout (src, tests, docs, etc.).\n2. Initialize version control (e.g., git init).\n3. Create basic config files (.gitignore, pyproject.toml, etc.).', 'status': 'pending', 'priority': 'high', 'dependencies': []},
        {'id': 2, 'title': 'Define core data models/schemas', 'description': '**Plan:**\n1. Identify key data structures.\n2. Implement using Pydantic, dataclasses, or similar.', 'status': 'pending', 'priority': 'medium', 'dependencies': [1]},
        {'id': 3, 'title': 'Implement basic feature X', 'description': '**Plan:**\n1. Define inputs and outputs.\n2. Implement core logic.\n3. Add basic error handling.', 'status': 'pending', 'priority': 'medium', 'dependencies': [2]},
        {'id': 4, 'title': 'Set up testing framework', 'description': '**Plan:**\n1. Choose testing framework (e.g., pytest).\n2. Add framework to dev dependencies.\n3. Create initial test file(s).', 'status': 'pending', 'priority': 'low', 'dependencies': [1]},
        {'id': 5, 'title': 'Set up CI/CD pipeline', 'description': '**Plan:**\n1. Choose CI/CD platform (e.g., GitHub Actions).\n2. Create basic workflow (lint, test).\n3. Configure triggers.', 'status': 'pending', 'priority': 'low', 'dependencies': [1, 4]},
    ]

    # --- Construct YAML Content --- 
    project_dict = {
        'project': {'name': project_name, 'version': project_version},
        'context': context_template,
        'tasks': tasks_template
    }

    try:
        # Use safe_dump and disable aliases for cleaner output
        yaml_content = yaml.safe_dump(
            project_dict, 
            default_flow_style=False, 
            sort_keys=False, 
            allow_unicode=True, 
            indent=2 # Ensure proper indentation for lists
        )
    except Exception as e:
         click.echo(f"Error generating YAML content: {e}", err=True)
         sys.exit(1)

    # --- Write File --- 
    try:
        with open(PLAN_FILENAME, "w", encoding="utf-8") as f:
            f.write(collaboration_guide) # Write the header comment first
            f.write("\n") # Add a newline
            f.write(yaml_content)
        click.echo(f"Successfully created {PLAN_FILENAME}!")
    except IOError as e:
        click.echo(f"Error writing file {PLAN_FILENAME}: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred during file writing: {e}", err=True)
        sys.exit(1)


@click.command("tui")
# TODO: Add option for plan file path: @click.option("--plan", default="PROJECT_PLAN.yaml", type=click.Path(exists=False, path_type=pathlib.Path))
def run_tui():
    """Launch the Textual TUI interface (requires TUI dependencies)."""
    tui_deps = ["textual", "watchdog", "pyperclip"]
    missing_deps = []
    for dep in tui_deps:
        spec = importlib.util.find_spec(dep)
        if spec is None:
            missing_deps.append(dep)

    if missing_deps:
        click.echo(f"Error: Missing TUI dependencies: {', '.join(missing_deps)}", err=True)
        click.echo("Please install them using: pip install metsuke[tui]", err=True)
        sys.exit(1)

    # Import TUI app only after checking dependencies
    try:
        from .tui.app import TaskViewer
    except ImportError as e:
        # This might happen if TUI code itself has issues
        click.echo(f"Error importing TUI components: {e}", err=True)
        click.echo("Ensure the TUI code is structured correctly in src/metsuke/tui/", err=True)
        sys.exit(1)

    # Default plan file path for now
    plan_path = pathlib.Path("PROJECT_PLAN.yaml")

    # Instantiate and run the app
    try:
        app = TaskViewer(plan_file=plan_path)
        app.run()
    except Exception as e:
        click.echo(f"Error running TUI: {e}", err=True)
        # Optionally log the full traceback here
        sys.exit(1) 