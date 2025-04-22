# -*- coding: utf-8 -*-
"""Command-line interface for Metsuke."""

import click
from pathlib import Path
from typing import Optional

# Import commands from cli.py
from .cli import show_info, list_tasks, run_tui, init, add_plan, update_plan

@click.group()
@click.version_option()
@click.option('--plan', 'plan_path_option', type=click.Path(exists=False, path_type=Path), default=None, help='Specify a plan file or directory.')
def main(plan_path_option: Optional[Path]):
    """Metsuke: Manage project plans for robust AI collaboration.

    This CLI helps manage project plans stored in YAML files (like
    PROJECT_PLAN.yaml or files in a plans/ directory). It provides tools
    to initialize plans, view project info and tasks, and interact with
    plans via a Terminal UI (TUI).

    Use `metsuke init` to create a starting plan file.
    Use `metsuke tui` to launch the interactive interface.
    """
    pass

# Add commands to the main group
main.add_command(show_info)
main.add_command(list_tasks)
main.add_command(run_tui)
main.add_command(init)
main.add_command(add_plan)
main.add_command(update_plan)

if __name__ == "__main__":
    main() # pragma: no cover 