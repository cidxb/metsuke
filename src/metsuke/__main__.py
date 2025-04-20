# -*- coding: utf-8 -*-
"""Command-line interface for Metsuke."""

import click

# Import commands from cli.py
from .cli import show_info, list_tasks, run_tui, init

@click.group()
@click.version_option()
def main():
    """Metsuke: AI-Assisted Development Task Manager CLI."""
    pass

# Add commands to the main group
main.add_command(show_info)
main.add_command(list_tasks)
main.add_command(run_tui)
main.add_command(init)

if __name__ == "__main__":
    main() # pragma: no cover 