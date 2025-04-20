# -*- coding: utf-8 -*-
"""Modal screens used in the Metsuke TUI."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, Markdown
from textual.screen import ModalScreen

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
        ("escape,q", "close_help", "Close"),
        # Add other bindings if they should be screen-specific
    ]

    def __init__(self, plan_context: str):
        super().__init__()
        self.plan_context = plan_context

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("[b]Help / Context[/b]", classes="title")
            yield Markdown(self.plan_context or "_No context provided in PROJECT_PLAN.yaml_", classes="context")
            yield Static("[u]Key Bindings:[/u]\n" # App-level bindings shown here
                         " Q / Esc : Close Help / Quit App\n"
                         " Ctrl+L  : Copy Log to Clipboard\n"
                         " Ctrl+D  : Toggle Log Panel Visibility\n"
                         " Ctrl+P  : Open Command Palette (theme, etc.)\n"
                         " ?       : Show this Help Screen", classes="bindings")
            yield Static("Press Esc or Q to close.", classes="close-hint")

    def action_close_help(self) -> None:
        self.app.pop_screen()

    # Note: App-level bindings like copy_log, toggle_log are handled by the main app 