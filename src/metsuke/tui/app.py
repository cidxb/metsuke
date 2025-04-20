# -*- coding: utf-8 -*-
"""Main Textual application class for the Metsuke TUI."""

import logging
# import yaml # Will be removed when Task 10 is done
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import Counter

# Conditional imports (ensure these are handled in handlers.py/screens.py)
try:
    from watchdog.observers import Observer # type: ignore
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    class Observer: pass # Dummy

try:
    import pyperclip # type: ignore
    _PYPERCLIP_AVAILABLE = True
except ImportError:
    _PYPERCLIP_AVAILABLE = False

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Header, Static, DataTable, ProgressBar, Log, Markdown
from textual.reactive import var
# from textual.screen import ModalScreen # Imported in screens.py

# Import from our TUI modules
from .widgets import (
    TitleDisplay, ProjectInfo, TaskProgress,
    PriorityBreakdown, DependencyStatus, AppFooter
)
from .screens import HelpScreen
from .handlers import TuiLogHandler, PlanFileEventHandler, _WATCHDOG_AVAILABLE as _HANDLER_WATCHDOG # Use flag from handler
from ..models import Project, Task, ProjectMeta # Import Pydantic models
from ..core import load_plan # Will be used in Task 10
from ..exceptions import PlanLoadingError, PlanValidationError # Will be used in Task 10

# PLAN_FILE = Path("PROJECT_PLAN.yaml") # Define this where TUI is launched or pass as arg


class TaskViewer(App):
    """A Textual app to view project tasks from PROJECT_PLAN.yaml."""

    # Moved CSS here from Metsuke.py __main__ block
    CSS = """
    Screen {
        background: $surface;
        color: $text;
        layout: vertical;
    }
    TitleDisplay {
        width: 100%;
        text-align: center;
        height: auto;
        margin-bottom: 1; /* Restored margin */
    }
    ProjectInfo {
        width: 100%;
        height: auto;
        border: thick $accent; /* Restored border */
        padding: 0 1;
        text-align: center;
        /* margin-bottom: 1; */ /* Removed margin, handled by HeaderInfo */
    }
    /* Re-add Style for Header Info */
    /* HeaderInfo {
        height: 1;
        width: 100%;
        text-align: right;
        color: $text-muted;
        padding: 0 1;
        margin-bottom: 1;
    } */ /* HeaderInfo might not be a widget */
    Container#main-container { /* Style the main content area */
        height: 1fr;
    }
    #dashboard {
        height: auto;
        border: thick $accent; /* Restored border */
        margin-bottom: 1; /* Restored margin */
    }
    #left-panel, #right-panel {
        width: 1fr;
        border: thick $accent; /* Restored border */
        padding: 1; /* Restored padding */
        height: auto;
    }
    #task-table {
        height: 1fr;
        border: thick $accent; /* Restored border */
    }
    /* Styles for widgets inside panels */
    TaskProgress {
        height: auto;
        margin-bottom: 1;
        width: 100%; /* Keep this change */
    }
    #progress-text {
        height: auto;
        width: 100%; /* Keep this change */
        text-align: center; /* Keep this change */
    }
    #overall-progress-bar {
        width: 100%;
        height: 1;
        margin-top: 1;
        align: center middle; /* Keep this change */
    }
    PriorityBreakdown, DependencyStatus {
        height: auto;
        margin-bottom: 1;
        width: 100%; /* Keep this change */
        text-align: center; /* Keep this change */
    }
    DataTable {
        height: auto; /* Let the container handle height */
    }
    Log {
        height: 8; /* Example height, adjust as needed */
        border-top: thick $accent; /* Restored border */
        /* margin-top: 1; */ /* Add space above log if desired */
        display: none; /* Hide log by default */
    }
    /* Style for Author Info - handled by StatusBar */
    /* #status-bar {
        height: 1;
        dock: bottom;
    } */

    /* New styles for AppFooter */
    AppFooter { /* Target the container directly */
        dock: bottom;
        height: 1;
        /* Use grid layout for better control */
        /* grid-size: 2; */ /* Replaced grid with horizontal layout */
        /* grid-gutter: 1 2; */
        layout: horizontal; /* Use horizontal layout */
        /* background: $accent-darken-1; */ /* Optional background */
    }
    AppFooter > #footer-bindings { /* Target child Static by ID */
        /* grid-column: 1; */ /* Removed grid property */
        content-align: left middle;
        width: 1fr; /* Changed from auto to take available space */
        overflow: hidden;
    }
    AppFooter > #footer-info { /* Target child Static by ID */
        /* grid-column: 2; */ /* Removed grid property */
        content-align: right middle;
        width: auto; /* Takes needed space */
    }
    """

    # Bindings moved from Metsuke.py
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+l", "copy_log", "Copy Log"),
        ("ctrl+d", "toggle_log", "Toggle Log"),
        ("ctrl+p", "command_palette", "Palette"), # Enable command palette
        ("?", "show_help", "Help")
    ]

    # Reactive variables moved from Metsuke.py
    # plan_data: var[Optional[PlanData]] = var(None, init=False) # OLD TypedDict version
    plan_data: var[Optional[Project]] = var(None, init=False) # NEW Pydantic version (used after Task 10)
    plan_context: var[str] = var("")
    last_load_time: var[Optional[datetime]] = var(None, init=False)
    observer: var[Optional[Observer]] = var(None, init=False)  # Store observer
    plan_file_path: Path # To be set on init

    # Class logger for the App itself
    # Use hierarchical naming
    app_logger = logging.getLogger("metsuke.tui.app") # Updated logger name

    # Store handler for copy action
    tui_handler: Optional[TuiLogHandler] = None

    # Initialize with the path to the plan file
    def __init__(self, plan_file: Path = Path("PROJECT_PLAN.yaml")):
        super().__init__()
        self.plan_file_path = plan_file
        self._load_data()  # Load data on initialization

    def compose(self) -> ComposeResult:
        # yield Header() # Removed Header widget for now
        yield TitleDisplay(id="title")
        yield ProjectInfo(id="project-info")
        with Container(id="main-container"):
            with Horizontal(id="dashboard"):
                with VerticalScroll(id="left-panel"):
                    yield TaskProgress(id="task-progress")
                    yield PriorityBreakdown(id="priority-breakdown")
                with VerticalScroll(id="right-panel"):
                    yield DependencyStatus(id="dependency-status")
            yield DataTable(id="task-table")
        yield Log(id="log-view", max_lines=200, highlight=True)
        yield AppFooter(bindings=self.BINDINGS, id="app-footer")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Setup TUI logging handler
        log_widget = self.query_one(Log)
        self.tui_handler = TuiLogHandler(log_widget)
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s: %(message)s\n', datefmt='%H:%M:%S')
        self.tui_handler.setFormatter(formatter)

        # Configure metsuke.tui logger (don't configure root logger from here)
        tui_logger = logging.getLogger("metsuke.tui")
        tui_logger.setLevel(logging.INFO) # Set level for TUI logs
        # Avoid adding handler if already added (e.g., if app restarts)
        if self.tui_handler not in tui_logger.handlers:
             tui_logger.addHandler(self.tui_handler)
        tui_logger.propagate = False # Don't pass logs up to root

        self.app_logger.info("TUI Log Handler configured. Press Ctrl+L to copy log.")

        self.update_ui()
        self.start_file_observer()
        self.query_one(DataTable).focus()

    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        self.stop_file_observer()  # Stop watchdog observer
        # Clean up logger handler
        if self.tui_handler:
            tui_logger = logging.getLogger("metsuke.tui")
            tui_logger.removeHandler(self.tui_handler)
            self.tui_handler = None

    def start_file_observer(self) -> None:
        """Starts the watchdog file observer."""
        if not _HANDLER_WATCHDOG:
             self.app_logger.warning("Watchdog not installed. File changes will not be detected.")
             return
        if not self.plan_file_path.exists():
            self.app_logger.warning(f"Cannot watch {self.plan_file_path} - file does not exist.")
            return

        event_handler = PlanFileEventHandler(self, self.plan_file_path)
        self.observer = Observer()
        watch_path = str(self.plan_file_path.parent.resolve())
        try:
            self.observer.schedule(event_handler, watch_path, recursive=False)
            self.observer.daemon = True
            self.observer.start()
            self.app_logger.info(f"Started watching {watch_path} for changes to {self.plan_file_path.name}")
        except Exception as e:
            self.app_logger.error(f"Failed to start file observer: {e}")
            self.observer = None


    def stop_file_observer(self) -> None:
        """Stops the watchdog file observer."""
        if self.observer and self.observer.is_alive():
            try:
                self.observer.stop()
                self.observer.join()
                self.app_logger.info("Stopped file observer.")
            except Exception as e:
                self.app_logger.error(f"Error stopping file observer: {e}")
        self.observer = None

    def reload_plan_data(self) -> None:
        """Reloads data and updates UI (called from watchdog thread via call_from_thread)."""
        self.app_logger.info("Reloading plan data due to file change...")
        self._load_data()
        self.update_ui()

    # TODO: Task 10 - Refactor this method to use core.load_plan
    def _load_data(self) -> None:
        """Loads data using the core load_plan function."""
        try:
            self.plan_data = load_plan(self.plan_file_path)
            self.plan_context = self.plan_data.context or ""
            self.last_load_time = datetime.now()
            self.app_logger.info(f"Plan data loaded successfully using core.load_plan for {self.plan_file_path}")

        except (PlanLoadingError, PlanValidationError) as e:
            self.app_logger.error(f"Failed to load or validate plan file: {e}")
            self.notify(f"Error: {e}", title="Plan Load Error", severity="error")
            self.plan_data = None
            self.plan_context = ""
        except Exception as e:
            # Catch any other unexpected errors during loading
            self.app_logger.exception(f"Unexpected error in _load_data: {e}") # Use exception logger
            self.notify(f"Unexpected error loading plan: {e}", title="Load Error", severity="error")
            self.plan_data = None
            self.plan_context = ""

    # TODO: Task 10 - Update this method to work with Project Pydantic object
    def update_ui(self) -> None:
        """Updates all UI components with the latest data."""
        self.app_logger.info("Updating UI...")
        if not self.plan_data: # Check if Project object is None
            self.app_logger.warning("No plan data object found, clearing UI.")
            self.query_one(ProjectInfo).meta = None
            table = self.query_one(DataTable)
            table.clear(columns=True)
            table.add_columns("ID", "Title", "Status", "Priority", "Dependencies")
            table.add_row("[i]No data loaded. Check PROJECT_PLAN.yaml[/i]", span=5)
            # Clear stats
            try:
                self.query_one(TaskProgress).update_progress(Counter(), 0.0)
                self.query_one(PriorityBreakdown).priority_counts = Counter()
                self.query_one(DependencyStatus).update_metrics({}) # Use update method
            except Exception as e:
                self.app_logger.error(f"Error clearing stats widgets: {e}")
            return

        # Access data via Pydantic model attributes
        project_meta = self.plan_data.project
        tasks = self.plan_data.tasks # List[Task]

        self.query_one(ProjectInfo).meta = project_meta

        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Title", "Status", "Priority", "Dependencies")
        table.fixed_columns = 1
        table.cursor_type = "row"
        for task in tasks: # task is now a Task Pydantic object
            deps_str = ", ".join(map(str, task.dependencies)) or "None"
            status_styled = f"[{self._get_status_color(task.status)}]{task.status}[/]"
            priority_styled = f"[{self._get_priority_color(task.priority)}]{task.priority}[/]"
            table.add_row(
                str(task.id),
                task.title,
                status_styled,
                priority_styled,
                deps_str,
                key=str(task.id),
            )

        if tasks:
            total_tasks = len(tasks)
            status_counts = Counter(t.status for t in tasks)
            priority_counts = Counter(t.priority for t in tasks)
            done_count = status_counts.get("Done", 0)
            progress_percent = (done_count / total_tasks) * 100 if total_tasks > 0 else 0

            self.app_logger.info(f"Calculated status_counts: {status_counts}")
            self.app_logger.info(f"Calculated progress_percent: {progress_percent:.1f}%")
            self.app_logger.info(f"Calculated priority_counts: {priority_counts}")

            self.query_one(TaskProgress).update_progress(status_counts, progress_percent)
            self.query_one(PriorityBreakdown).priority_counts = priority_counts
            self.query_one(PriorityBreakdown).refresh() # Refresh static widgets

            dep_metrics = self._calculate_dependency_metrics(tasks)
            self.app_logger.info(f"Calculated dep_metrics: {dep_metrics}")
            self.query_one(DependencyStatus).update_metrics(dep_metrics) # Use update method

        else:
            self.app_logger.info("Clearing statistics as no tasks found.")
            self.query_one(TaskProgress).update_progress(Counter(), 0.0)
            self.query_one(PriorityBreakdown).priority_counts = Counter()
            self.query_one(PriorityBreakdown).refresh()
            self.query_one(DependencyStatus).update_metrics({}) # Use update method

    # Helper methods remain mostly the same, accepting Task objects
    def _get_status_color(self, status: str) -> str:
        return {
            "Done": "green",
            "in_progress": "yellow",
            "pending": "blue",
            "blocked": "red",
        }.get(status, "white")

    def _get_priority_color(self, priority: str) -> str:
        return {
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }.get(priority, "white")

    # This method now takes List[Task] Pydantic objects
    def _calculate_dependency_metrics(self, tasks: List[Task]) -> Dict[str, Any]:
        if not tasks:
            return {}

        task_map = {t.id: t for t in tasks}
        done_ids = {t.id for t in tasks if t.status == "Done"}
        dependents_count = Counter()
        total_deps = 0
        no_deps_count = 0
        blocked_by_deps_count = 0
        ready_tasks: List[Task] = [] # Explicitly type

        for task in tasks:
            deps = task.dependencies
            total_deps += len(deps)
            if not deps:
                no_deps_count += 1

            is_blocked = False
            for dep_id in deps:
                dependents_count[dep_id] += 1
                if dep_id not in done_ids:
                    is_blocked = True

            if task.status != "Done":
                if is_blocked:
                    blocked_by_deps_count += 1
                else:
                    ready_tasks.append(task)

        most_depended = dependents_count.most_common(1)
        most_depended_id = most_depended[0][0] if most_depended else None
        most_depended_count = most_depended[0][1] if most_depended else 0

        next_task: Optional[Task] = None # Explicitly type
        if ready_tasks:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            ready_tasks.sort(
                key=lambda t: (priority_order.get(t.priority, 99), t.id)
            )
            next_task = ready_tasks[0]

        return {
            "no_deps": no_deps_count,
            "ready_to_work": len(ready_tasks),
            "blocked_by_deps": blocked_by_deps_count,
            "most_depended_id": most_depended_id,
            "most_depended_count": most_depended_count,
            "avg_deps": total_deps / len(tasks) if tasks else 0.0,
            "next_task": next_task, # Store the Task object itself
        }

    # Action methods moved from Metsuke.py
    def action_copy_log(self) -> None:
        """Copies the current log content to the clipboard."""
        if not _PYPERCLIP_AVAILABLE:
             self.app_logger.error("Pyperclip not installed. Cannot copy log.")
             self.notify("Pyperclip not installed. Cannot copy log.", title="Error", severity="error")
             return

        if self.tui_handler and self.tui_handler.messages:
            log_content = "\n".join(self.tui_handler.messages)
            try:
                pyperclip.copy(log_content)
                msg = f"{len(self.tui_handler.messages)} log lines copied to clipboard."
                self.app_logger.info(msg)
                self.notify(msg, title="Log Copied")
            except Exception as e:
                self.app_logger.error(f"Failed to copy log to clipboard: {e}")
                self.notify(f"Failed to copy log: {e}", title="Error", severity="error")
        elif self.tui_handler:
             self.app_logger.info("Log is empty, nothing to copy.")
             self.notify("Log is empty, nothing to copy.", title="Log Copy")
        else:
             self.app_logger.warning("Log handler not ready, cannot copy.")
             self.notify("Log handler not ready.", title="Error", severity="warning")


    def action_toggle_log(self) -> None:
        """Toggles the visibility of the log view panel."""
        try:
            log_widget = self.query_one(Log)
            log_widget.display = not log_widget.display
            self.app_logger.info(f"Log view display toggled {'on' if log_widget.display else 'off'}.")
        except Exception as e:
            self.app_logger.error(f"Error toggling log display: {e}")

    def action_show_help(self) -> None:
        """Shows the help/context modal screen."""
        # Pass the context loaded from the plan data
        self.push_screen(HelpScreen(plan_context=self.plan_context))

    # Action to enable command palette (uses default Textual action)
    # def action_command_palette(self) -> None:
    #     self.app.action_command_palette() # This should be handled automatically by Textual if binding exists

# Note: The part that runs the app (`if __name__ == "__main__":`) is NOT copied here.
# It will be handled by the CLI entry point (Task 11). 