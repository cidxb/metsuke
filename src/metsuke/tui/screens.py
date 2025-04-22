# -*- coding: utf-8 -*-
"""Modal screens used in the Metsuke TUI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, Markdown, DataTable
from textual.screen import ModalScreen
from textual.binding import Binding
from pathlib import Path
from typing import Dict, Optional
from rich.text import Text
from ..models import Project
import logging

# Conditional import for pyperclip
try:
    import pyperclip # type: ignore
    _PYPERCLIP_AVAILABLE = True
except ImportError:
    _PYPERCLIP_AVAILABLE = False


class HelpScreen(ModalScreen):
    """Modal screen to display help and context."""

    CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Container {
        width: 75%;
        max-width: 90%;
        max-height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    HelpScreen .title { width: 100%; text-align: center; margin-bottom: 1; }
    HelpScreen .context { margin-bottom: 1; border: round $accent-lighten-1; padding: 1; max-height: 25; overflow-y: auto; }
    HelpScreen .bindings { margin-bottom: 1; border: round $accent-lighten-1; padding: 1; }
    HelpScreen .close-hint { width: 100%; text-align: center; margin-top: 1; color: $text-muted; }
    """

    BINDINGS = [
        Binding("escape", "close_help", "Close", show=False),
    ]

    def __init__(self, plan_context: str):
        super().__init__()
        self.plan_context = plan_context

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("[b]Help & Context[/b]", classes="title")
            yield Markdown(f"**Current Context:**\n```\n{self.plan_context}\n```", classes="context")
            yield Static("[b]Key Bindings[/b]", classes="bindings")
            yield Markdown("""\
*   `Ctrl+C`: Quit
*   `Ctrl+B`: Select Focus Plan
*   `Ctrl+S`: Save Current Plan
*   `Ctrl+A`: Add new task/subtask
*   `Ctrl+E`: Edit selected task/subtask
*   `Ctrl+D`: Toggle task done/pending
*   `Delete`: Delete selected task/subtask
*   `Up/Down`: Navigate tasks
*   `Left/Right`: Navigate focus plans
*   `?`: Show this help screen\
""")
            yield Static("Press Esc to close.", classes="close-hint")

    def action_close_help(self) -> None:
        """Called when the user presses escape."""
        self.dismiss()

    # Note: App-level bindings like copy_log, toggle_log are handled by the main app 

# --- PlanSelectionScreen Removed --- 

# class PlanSelectionScreen(ModalScreen[Optional[Path]]): 
#     # ... (Entire class definition deleted) ... 