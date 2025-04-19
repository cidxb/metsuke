# -*- coding: utf-8 -*-
"""Command-line interface for Metsuke."""

import click

# Placeholder: Import commands from cli.py later
# from .cli import show_info, list_tasks

@click.group()
@click.version_option()
def main():
    """Metsuke: AI-Assisted Development Task Manager CLI."""
    pass

# Placeholder: Add commands later
# main.add_command(show_info)
# main.add_command(list_tasks)

if __name__ == "__main__":
    main() # pragma: no cover 