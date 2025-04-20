# -*- coding: utf-8 -*-
"""Event handlers for the Metsuke TUI (Logging, File Watching)."""

import logging
from collections import deque
from pathlib import Path

from textual.app import App
from textual.widgets import Log

# Conditional import for watchdog, only needed if running the TUI
try:
    from watchdog.observers import Observer # type: ignore
    from watchdog.events import FileSystemEventHandler # type: ignore
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    # Define dummy classes if watchdog is not installed
    class Observer: # type: ignore
        pass
    class FileSystemEventHandler: # type: ignore
        pass


PLAN_FILE = Path("PROJECT_PLAN.yaml") # Assuming default, might need to be passed in

# --- TUI Log Handler ---
class TuiLogHandler(logging.Handler):
    """A logging handler that writes records to a Textual Log widget."""
    def __init__(self, log_widget: Log):
        super().__init__()
        self.log_widget = log_widget
        # Store messages in a deque with max length matching the widget
        self.messages = deque(maxlen=getattr(log_widget, 'max_lines', None) or 200)

    def emit(self, record):
        try:
            msg = self.format(record)
            # Use call_from_thread to safely update the widget from any thread
            # self.log_widget.app.call_from_thread(self.log_widget.write, msg) # Old line
            self.log_widget.write(msg) # New line - direct write
            self.messages.append(msg) # Also store the message
        except Exception:
            self.handleError(record)

# --- Watchdog Event Handler ---
class PlanFileEventHandler(FileSystemEventHandler):
    """Handles file system events for PROJECT_PLAN.yaml."""

    def __init__(self, app: App, file_path: Path):
        if not _WATCHDOG_AVAILABLE:
             raise RuntimeError("Watchdog library is not installed. Cannot watch file.")
        self.app = app
        self.file_path = file_path.resolve()  # Get absolute path

    def on_modified(self, event):
        """Called when a file or directory is modified."""
        # Check if the modified file is the one we are watching
        # event.src_path gives the path of the modified item
        if not event.is_directory and Path(event.src_path).resolve() == self.file_path:
            # Safely call the app's reload method from the watchdog thread
            # Check if the target method exists before calling
            if hasattr(self.app, "reload_plan_data") and callable(getattr(self.app, "reload_plan_data")):
                 self.app.call_from_thread(self.app.reload_plan_data)
            else:
                 # Log a warning if the method is missing (perhaps during development)
                 pass # Or log using a standard logger if TUI isn't ready 