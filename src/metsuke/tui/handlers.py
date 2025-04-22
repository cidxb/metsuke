# -*- coding: utf-8 -*-
"""Event handlers for the Metsuke TUI (Logging, File Watching)."""

import logging
from collections import deque
from pathlib import Path
import time # Import time for potential debouncing
from typing import Dict, Optional # Add missing import

from textual.app import App
from textual.widgets import Log

# Conditional import for watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent, DirModifiedEvent, DirCreatedEvent, DirDeletedEvent # Import specific events
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    class Observer: pass
    class FileSystemEventHandler: pass
    # Define dummy event classes if needed
    class FileModifiedEvent: pass
    class FileCreatedEvent: pass
    class FileDeletedEvent: pass
    class DirModifiedEvent: pass
    class DirCreatedEvent: pass
    class DirDeletedEvent: pass


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


# --- Watchdog Event Handler (Modified) ---
class DirectoryEventHandler(FileSystemEventHandler):
    """Handles file system events within a specified directory for specific patterns."""

    # Debounce settings (optional, adjust as needed)
    DEBOUNCE_DELAY = 0.5 # seconds

    def __init__(self, app: App, watch_path: Path, file_pattern: str):
        if not _WATCHDOG_AVAILABLE:
            raise RuntimeError("Watchdog library is not installed. Cannot watch directory.")
        self.app = app
        self.watch_path = watch_path.resolve()
        self.file_pattern = file_pattern # e.g., "PROJECT_PLAN_*.yaml" or "PROJECT_PLAN.yaml"
        self.logger = logging.getLogger(__name__)
        self._last_event_time: Dict[Path, float] = {} # For debouncing

    def _should_process(self, event_path_str: str) -> Optional[Path]:
        """Check if the event path matches the pattern and handle debouncing."""
        event_path = Path(event_path_str).resolve()

        # Ignore events for directories themselves, only care about files within
        if event_path.is_dir():
             return None

        # Check if the file matches the pattern relative to the watched path
        try:
             # Ensure the event path is within the watched directory
             relative_path = event_path.relative_to(self.watch_path)
             # Check glob pattern match on the filename
             if not event_path.match(self.file_pattern):
                  # self.logger.debug(f"Ignoring event for non-matching pattern: {event_path.name}")
                  return None
        except ValueError:
             # Event path is not within the watched directory (shouldn't happen with non-recursive watch)
             self.logger.warning(f"Event path {event_path} outside watch path {self.watch_path}.")
             return None

        # Debouncing logic
        now = time.monotonic()
        last_time = self._last_event_time.get(event_path, 0)
        if (now - last_time) < self.DEBOUNCE_DELAY:
            # self.logger.debug(f"Debouncing event for: {event_path.name}")
            return None # Debounce

        self._last_event_time[event_path] = now
        return event_path # Path matches and is not debounced

    def _dispatch_to_app(self, event_type: str, path: Path):
         """Safely calls the app's handler method."""
         if hasattr(self.app, "handle_file_change") and callable(getattr(self.app, "handle_file_change")):
              self.logger.info(f"Dispatching '{event_type}' event for {path.name} to app.")
              # Use call_from_thread as watchdog runs in a separate thread
              self.app.call_from_thread(self.app.handle_file_change, event_type=event_type, path=path)
         else:
              self.logger.error("App instance is missing the 'handle_file_change' method!")


    def on_modified(self, event: FileModifiedEvent | DirModifiedEvent):
        """Called when a file or directory is modified."""
        if isinstance(event, FileModifiedEvent):
             path = self._should_process(event.src_path)
             if path:
                  self._dispatch_to_app("modified", path)

    def on_created(self, event: FileCreatedEvent | DirCreatedEvent):
        """Called when a file or directory is created."""
        if isinstance(event, FileCreatedEvent):
            path = self._should_process(event.src_path)
            if path:
                self._dispatch_to_app("created", path)

    def on_deleted(self, event: FileDeletedEvent | DirDeletedEvent):
        """Called when a file or directory is deleted."""
        # Resolve path before checking pattern, as file doesn't exist anymore
        # We need to know if the *deleted* path matched our interest.
        # For simplicity, we might check the parent dir and filename pattern.
        deleted_path = Path(event.src_path).resolve()
        watch_path_str = str(self.watch_path)
        deleted_path_str = str(deleted_path)

        # Check if deleted file was directly in our watch path and matched pattern
        if deleted_path.parent == self.watch_path and deleted_path.match(self.file_pattern):
             # No debouncing needed/possible for deletion of the key itself
             self.logger.info(f"Detected deletion of matching file: {deleted_path.name}")
             self._dispatch_to_app("deleted", deleted_path)
        # else: ignore deletion of non-matching files/subdirs

    # on_moved can be complex, potentially treat as delete + create
    # For simplicity, we might ignore moves or rely on separate create/delete events
    # def on_moved(self, event):
    #     pass

# Remove old PlanFileEventHandler
# class PlanFileEventHandler(FileSystemEventHandler):
# ... (old implementation) ... 