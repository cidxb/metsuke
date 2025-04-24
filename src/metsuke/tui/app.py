# -*- coding: utf-8 -*-
"""Main Textual application class for the Metsuke TUI."""

import logging

# import yaml # Will be removed when Task 10 is done
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Type
from collections import Counter

# Conditional imports (ensure these are handled in handlers.py/screens.py)
try:
    from watchdog.observers import Observer  # type: ignore

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False

    class Observer:
        pass  # Dummy


try:
    import pyperclip  # type: ignore

    _PYPERCLIP_AVAILABLE = True
except ImportError:
    _PYPERCLIP_AVAILABLE = False

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Header, Static, DataTable, ProgressBar, Log, Markdown
from textual.reactive import var
from textual.screen import Screen
from textual.binding import Binding
from textual import events  # Added import
from rich.text import Text  # Added import for plan selection table

# Import from our TUI modules
from .widgets import (
    TitleDisplay,
    ProjectInfo,
    TaskProgress,
    PriorityBreakdown,
    DependencyStatus,
    AppFooter,
)
from .screens import HelpScreen  # Only HelpScreen needed now
from .handlers import (
    TuiLogHandler,
    DirectoryEventHandler,
    _WATCHDOG_AVAILABLE as _HANDLER_WATCHDOG,
)  # Use new handler
from ..models import Project, Task, ProjectMeta  # Import Pydantic models
from ..core import load_plans, manage_focus, save_plan  # Import new core functions
from ..exceptions import (
    PlanLoadingError,
    PlanValidationError,
)  # Will be used in Task 10

# PLAN_FILE = Path("PROJECT_PLAN.yaml") # Define this where TUI is launched or pass as arg


class TaskViewer(App):
    """A Textual app to view project tasks from PROJECT_PLAN.yaml."""

    # Moved CSS here from Metsuke.py __main__ block
    CSS = """
    Screen {
        background: $surface;
        color: $text; /* Default text color */
        layout: vertical;
    }
    TitleDisplay {
        width: 100%;
        text-align: center;
        height: auto;
        margin-bottom: 1; /* Restored margin */
        color: $primary; /* Apply primary color to title, author part overridden by [dim] */
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
    #plan-selection-table {
        height: 1fr; /* Occupy available space like task-table */
        border: thick $accent;
        display: none; /* Hide by default */
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
        # Add back 'q' for quitting, along with Ctrl+C
        Binding("q", "quit", "Quit", show=True, priority=True), # Added back, NOW VISIBLE
        Binding(
            "ctrl+c", "quit", "Quit", priority=True, show=True
        ),  # Kept Ctrl+C as visible primary
        ("ctrl+l", "copy_log", "Copy Log"),
        ("ctrl+d", "toggle_log", "Toggle Log"),
        ("ctrl+b", "open_plan_selection", "Select Plan"),  # Changed description
        ("ctrl+p", "command_palette", "Palette"),  # Enable command palette
        ("?", "show_help", "Help"),
        # Add new bindings for arrow keys (not shown in help, but used for switching)
        Binding("left", "previous_plan", "Prev Plan", show=False, priority=True),
        Binding("right", "next_plan", "Next Plan", show=False, priority=True),
        # Add other app-level bindings here (e.g., task manipulation later)
    ]

    # Reactive variables moved from Metsuke.py
    plan_data: var[Optional[Project]] = var(
        None, init=False
    )  # Keep for now, may remove if unused
    plan_context: var[str] = var("")  # Keep for HelpScreen
    last_load_time: var[Optional[datetime]] = var(None, init=False)
    observer: var[Optional[Observer]] = var(None, init=False)  # Store observer
    # --- New reactive variables for managing multiple plans ---
    all_plans: var[Dict[Path, Optional[Project]]] = var({}, init=False)
    current_plan_path: var[Optional[Path]] = var(None, init=False)
    initial_plan_files: List[Path]
    # --- New state for plan selection view ---
    selecting_plan: var[bool] = var(False, init=False)
    # --- End new reactive variables ---

    # Class logger for the App itself
    app_logger = logging.getLogger("metsuke.tui.app")

    # Store handler for copy action
    tui_handler: Optional[TuiLogHandler] = None

    # --- Modified __init__ ---
    def __init__(self, plan_files: List[Path]):
        super().__init__()
        if not plan_files:
            # This should ideally be caught in cli.py, but double-check
            raise ValueError(
                "TaskViewer must be initialized with at least one plan file path."
            )
        self.initial_plan_files = plan_files
        # Removed _load_data() call - initial loading happens in on_mount
        self.app_logger.info(
            f"TUI initialized with {len(plan_files)} potential plan file(s)."
        )

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
            yield DataTable(id="plan-selection-table")  # Add plan selection table
        yield Log(id="log-view", max_lines=200, highlight=True)
        yield AppFooter(bindings=self.BINDINGS, id="app-footer")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Setup TUI logging handler
        log_widget = self.query_one(Log)
        self.tui_handler = TuiLogHandler(log_widget)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s\n", datefmt="%H:%M:%S"
        )
        self.tui_handler.setFormatter(formatter)

        # Configure metsuke.tui logger (don't configure root logger from here)
        tui_logger = logging.getLogger("metsuke.tui")
        tui_logger.setLevel(logging.DEBUG) # Set level to DEBUG to see detailed logs
        # Avoid adding handler if already added (e.g., if app restarts)
        if self.tui_handler not in tui_logger.handlers:
             tui_logger.addHandler(self.tui_handler)
        tui_logger.propagate = False  # Don't pass logs up to root

        self.app_logger.info("TUI Log Handler configured. Press Ctrl+L to copy log.")

        # Load initial data and determine focus (This calls update_ui internally)
        self._initial_load_and_focus()  # Corrected call

        # Start file observer AFTER initial load
        self.start_file_observer()

        # Focus the task table initially (if not selecting plan)
        if not self.selecting_plan:
            self.query_one("#task-table").focus()

    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        self.stop_file_observer()  # Stop watchdog observer
        # Clean up logger handler
        if self.tui_handler:
            tui_logger = logging.getLogger("metsuke.tui")
            tui_logger.removeHandler(self.tui_handler)
            self.tui_handler = None

    def start_file_observer(self) -> None:
        """Starts the watchdog file observer based on loaded plans."""
        if not _HANDLER_WATCHDOG:
            self.app_logger.warning(
                "Watchdog not installed. File changes will not be automatically detected."
            )
            return
        if not self.initial_plan_files:
            self.app_logger.warning(
                "No initial plan files found, cannot start observer."
            )
            return

        # Determine watch path and pattern
        first_plan_path = self.initial_plan_files[0]
        watch_path: Path
        file_pattern: str

        # Check if we are in multi-plan mode (plans/ dir exists and was used)
        # TODO: Get plans dir name and pattern from core constants?
        from ..core import PLANS_DIR_NAME, PLAN_FILE_PATTERN, DEFAULT_PLAN_FILENAME

        plans_dir = Path.cwd() / PLANS_DIR_NAME
        is_multi_mode = plans_dir.is_dir() and any(
            f.parent == plans_dir for f in self.initial_plan_files
        )

        if is_multi_mode:
            watch_path = plans_dir
            file_pattern = PLAN_FILE_PATTERN
            self.app_logger.info(
                f"Starting observer in multi-plan mode for directory: {watch_path}"
            )
        else:
            # Single file mode (either root PROJECT_PLAN.yaml or explicitly specified file)
            watch_path = first_plan_path.parent
            file_pattern = first_plan_path.name  # Watch only the specific file
            self.app_logger.info(
                f"Starting observer in single-plan mode for file: {first_plan_path}"
            )

        if not watch_path.exists():
            self.app_logger.error(
                f"Cannot start observer: Watch path does not exist: {watch_path}"
            )
            return

        event_handler = DirectoryEventHandler(self, watch_path, file_pattern)
        self.observer = Observer()
        try:
            # Watch the determined directory (non-recursive for simplicity)
            self.observer.schedule(
                event_handler, str(watch_path.resolve()), recursive=False
            )
            self.observer.daemon = True
            self.observer.start()
            self.app_logger.info(
                f"Observer started watching {watch_path.resolve()} for pattern '{file_pattern}'"
            )
        except Exception as e:
            self.app_logger.exception(f"Failed to start file observer for {watch_path}")
            self.observer = None  # Ensure observer is None if start fails

    def stop_file_observer(self) -> None:
        """Stops the watchdog file observer."""
        if self.observer and self.observer.is_alive():
            try:
                self.observer.stop()
                # Wait for the observer thread to finish
                self.observer.join(timeout=1.0)  # Add a timeout
                if self.observer.is_alive():
                    self.app_logger.warning("Observer thread did not join cleanly.")
                else:
                    self.app_logger.info("Stopped file observer.")
            except Exception as e:
                self.app_logger.exception("Error stopping file observer")
        self.observer = None  # Clear observer reference

    def handle_file_change(self, event_type: str, path: Path) -> None:
        """Callback for file changes detected by the handler."""
        self.app_logger.info(
            f"Handling file change event: {event_type} for {path.name}"
        )
        path = path.resolve()  # Ensure absolute path

        needs_focus_check = False
        needs_ui_update = False

        current_plans = self.all_plans.copy()  # Work on a copy

        if event_type == "modified":
            if path not in current_plans:
                self.app_logger.warning(
                    f"Modified event for untracked file: {path}. Ignoring."
                )
                return

            self.app_logger.info(f"Reloading modified plan: {path.name}")
            # Reload the single modified plan
            reloaded_plan_dict = load_plans([path])
            reloaded_plan = reloaded_plan_dict.get(path)  # Can be None if load fails

            # Check if load status changed or content actually changed
            if (
                current_plans.get(path) != reloaded_plan
            ):  # Basic check, might need deep compare
                current_plans[path] = reloaded_plan
                self.last_load_time = datetime.now()
                self.notify(f"Plan '{path.name}' reloaded.")
                if path == self.current_plan_path:
                    needs_ui_update = True
                # If the focus status changed in the file, we need to re-evaluate
                # Check if plan exists before accessing focus
                old_plan_focus = self.all_plans.get(path) and self.all_plans[path].focus
                new_plan_focus = current_plans.get(path) and current_plans[path].focus
                if new_plan_focus != old_plan_focus:
                    needs_focus_check = True
            else:
                self.app_logger.info(
                    f"Plan '{path.name}' reloaded, but content appears unchanged."
                )

        elif event_type == "created":
            if path in current_plans:
                self.app_logger.warning(
                    f"Created event for already tracked file: {path}. Reloading."
                )
                # Treat as modification
                reloaded_plan_dict = load_plans([path])
                current_plans[path] = reloaded_plan_dict.get(path)
            else:
                self.app_logger.info(f"Loading newly created plan: {path.name}")
                new_plan_dict = load_plans([path])
                current_plans[path] = new_plan_dict.get(
                    path
                )  # Add the new plan (or None if load failed)

            self.last_load_time = datetime.now()
            self.notify(f"New plan '{path.name}' detected.")
            # New plan might require focus check if it has focus: true
            if current_plans.get(path) and current_plans[path].focus:
                needs_focus_check = True
            # UI update needed if the plan list changes (for PlanSelectionScreen)
            # needs_ui_update = True # Maybe not needed immediately?

        elif event_type == "deleted":
            if path not in current_plans:
                self.app_logger.warning(
                    f"Deleted event for untracked file: {path}. Ignoring."
                )
                return

            self.app_logger.info(f"Removing deleted plan: {path.name}")
            was_focused = path == self.current_plan_path
            del current_plans[path]
            self.notify(f"Plan '{path.name}' removed.")

            if was_focused:
                self.app_logger.warning("The focused plan was deleted!")
                self.current_plan_path = None  # Clear current focus path immediately
                needs_focus_check = True  # Need to find a new focus
                needs_ui_update = True  # UI needs to reflect loss of focus

        # Update the main state variable
        self.all_plans = current_plans

        # Perform focus check if needed (this might save files)
        if needs_focus_check:
            self.app_logger.info("Re-evaluating focus due to file change...")
            updated_plans, new_focus_path = manage_focus(self.all_plans)
            self.all_plans = (
                updated_plans  # Update state again after manage_focus saves
            )
            if new_focus_path != self.current_plan_path:
                # Check if focus path actually exists before assigning
                if new_focus_path is None and len(self.all_plans) > 0:
                    # This case shouldn't happen if manage_focus works correctly, but handle defensively
                    self.app_logger.error(
                        "manage_focus returned None focus path despite valid plans existing!"
                    )
                    # Maybe try to pick one manually?
                    # For now, log error and potentially leave focus as None
                elif new_focus_path is not None:
                    self.app_logger.info(
                        f"Focus changed to {new_focus_path.name} after file event."
                    )
                    self.current_plan_path = new_focus_path
                    needs_ui_update = True  # Focus changed, update UI
                else:  # new_focus_path is None and no plans left
                    self.app_logger.info(
                        "No valid plans left after file event, focus is None."
                    )
                    self.current_plan_path = None
                    needs_ui_update = True  # UI should show no plan

        # Update UI if required
        if needs_ui_update:
            self.update_ui()
            # If we were selecting a plan and the list changed, refresh the selection table
            if self.selecting_plan:
                self._populate_plan_selection_table()
                # Try to keep focus on the selection table
                try:
                    self.query_one("#plan-selection-table").focus()
                except Exception:
                    self.app_logger.error(
                        "Failed to refocus plan selection table after file change."
                    )
            else:
                # Ensure focus is back on task table if not selecting
                try:
                    self.query_one("#task-table").focus()
                except Exception:
                    self.app_logger.error(
                        "Failed to refocus task table after file change."
                    )

    # --- Modified update_ui ---
    def update_ui(self) -> None:
        """Updates all UI components based on the current state."""
        # Update title/project info regardless of mode first
        current_plan = self.all_plans.get(self.current_plan_path)
        # --- Debug Logging Start ---
        self.app_logger.debug(f"update_ui: Updating ProjectInfo... current_plan_path={self.current_plan_path}, current_plan is None: {current_plan is None}")
        # --- Debug Logging End ---
        try:
            title_widget = self.query_one(TitleDisplay)
            project_info_widget = self.query_one(ProjectInfo)
            if current_plan:
                title_widget.update(f"[b cyan]Metsuke[/] - {current_plan.project.name}")
                # Call _render_display directly with required arguments
                project_info_widget._render_display(current_plan.project, self.current_plan_path)
            else:
                title_widget.update("[b cyan]Metsuke[/]")
                # Call _render_display directly with None for project
                project_info_widget._render_display(None, self.current_plan_path)
                if (
                    self.current_plan_path
                    and self.all_plans.get(self.current_plan_path) is None
                ):
                    # The _render_display call above already handles the display part
                    # We might still want to log the specific error here or notify
                    self.app_logger.warning(f"Error state detected for plan: {self.current_plan_path.name}")
        except Exception as e:
            self.app_logger.error(f"Error updating title/project info: {e}")

        # Update task-specific parts only if not selecting plan
        if not self.selecting_plan:
            self.app_logger.debug(
                f"Updating Task UI for plan: {self.current_plan_path}"
            )
            current_plan = self.all_plans.get(self.current_plan_path)

            if not current_plan:
                self.app_logger.warning(
                    "No plan data object found for task UI, clearing."
                )
                # Clear Task Table
                try:
                    table = self.query_one("#task-table", DataTable)
                    table.clear(columns=True)
                except Exception as e:
                    self.app_logger.error(f"Error clearing task table: {e}")
                # Clear Stats Widgets
                try:
                    self.query_one(TaskProgress).update_progress(Counter(), 0.0)
                    self.query_one(PriorityBreakdown).priority_counts = Counter()
                    self.query_one(DependencyStatus).update_metrics({})
                except Exception as e:
                    self.app_logger.error(f"Error clearing stats widgets: {e}")
            else:  # If current_plan is valid
                # Populate Task Table
                try:
                    tasks = current_plan.tasks
                    table = self.query_one("#task-table", DataTable)
                    table.clear(columns=True)
                    table.add_columns(
                        "ID", "Title", "Prio", "Status", "Deps"
                    )
                    table.fixed_columns = 1
                    for task in tasks:
                        deps_str = ", ".join(map(str, task.dependencies)) or "None"
                        status_styled = (
                            f"[{self._get_status_color(task.status)}]{task.status}[/]")
                        priority_styled = f"[{self._get_priority_color(task.priority)}]{task.priority}[/]"
                        table.add_row(
                            str(task.id),
                            task.title,
                            priority_styled,
                            status_styled,
                            deps_str,
                            key=str(task.id),
                        )
                except Exception as e:
                    self.app_logger.error(
                        f"Error populating task table: {e}", exc_info=True
                    )

                # Update Stats Widgets
                try:
                    if tasks:
                        total_tasks = len(tasks)
                        status_counts = Counter(t.status for t in tasks)
                        priority_counts = Counter(t.priority for t in tasks)
                        done_count = status_counts.get("Done", 0)
                        progress_percent = (
                            (done_count / total_tasks) * 100 if total_tasks > 0 else 0
                        )
                        self.query_one(TaskProgress).update_progress(
                            status_counts, progress_percent
                        )
                        self.query_one(
                            PriorityBreakdown
                        ).priority_counts = priority_counts
                        # Refresh static widgets like PriorityBreakdown after updating counts
                        self.query_one(PriorityBreakdown).refresh()
                        dep_metrics = self._calculate_dependency_metrics(tasks)
                        self.query_one(DependencyStatus).update_metrics(dep_metrics)
                    else:
                        # If there are no tasks, clear the stats
                        self.query_one(TaskProgress).update_progress(Counter(), 0.0)
                        self.query_one(PriorityBreakdown).priority_counts = Counter()
                        self.query_one(PriorityBreakdown).refresh()
                        self.query_one(DependencyStatus).update_metrics({})
                except Exception as e:
                    self.app_logger.error(
                        f"Error updating stats widgets: {e}", exc_info=True
                    )
        else:
            self.app_logger.debug("Skipping task UI update while selecting plan.")

        # Update footer info (this part seems ok)
        try:
            footer = self.query_one(AppFooter)
            footer.current_plan_path = self.current_plan_path
        except Exception as e:
            self.app_logger.error(f"Error updating footer info: {e}")

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
        ready_tasks: List[Task] = []  # Explicitly type

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

        next_task: Optional[Task] = None  # Explicitly type
        if ready_tasks:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            ready_tasks.sort(key=lambda t: (priority_order.get(t.priority, 99), t.id))
            next_task = ready_tasks[0]

        return {
            "no_deps": no_deps_count,
            "ready_to_work": len(ready_tasks),
            "blocked_by_deps": blocked_by_deps_count,
            "most_depended_id": most_depended_id,
            "most_depended_count": most_depended_count,
            "avg_deps": total_deps / len(tasks) if tasks else 0.0,
            "next_task": next_task,  # Store the Task object itself
        }

    # Action methods moved from Metsuke.py
    def action_copy_log(self) -> None:
        """Copies the current log content to the clipboard."""
        if not _PYPERCLIP_AVAILABLE:
            self.app_logger.error("Pyperclip not installed. Cannot copy log.")
            self.notify(
                "Pyperclip not installed. Cannot copy log.",
                title="Error",
                severity="error",
            )
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
            self.app_logger.info(
                f"Log view display toggled {'on' if log_widget.display else 'off'}."
            )
        except Exception as e:
            self.app_logger.error(f"Error toggling log display: {e}")

    def action_show_help(self) -> None:
        """Shows the help/context modal screen."""
        current_plan = self.all_plans.get(self.current_plan_path)
        context_text = current_plan.context if current_plan else "No context available."
        self.push_screen(HelpScreen(plan_context=context_text))

    # --- Modified action_open_plan_selection ---
    def action_open_plan_selection(self) -> None:
        """Toggles the plan selection view integrated into the main screen."""
        self.app_logger.info(f"Action: Toggle Plan Selection View. Current state: {self.selecting_plan}")
        if self.selecting_plan: # If currently selecting, turn it off
            self.selecting_plan = False
        else: # If not selecting, turn it on
            # Now, set the state to True, which will trigger the watch method.
            self.selecting_plan = True

    # --- New watch method for UI switching ---
    def watch_selecting_plan(self, selecting: bool) -> None:
        """Toggle visibility of widgets based on plan selection state."""
        self.app_logger.info(f"Watch selecting_plan: {selecting}")
        try:
            dashboard = self.query_one("#dashboard")
            task_table = self.query_one("#task-table", DataTable)
            plan_table = self.query_one("#plan-selection-table", DataTable)
            footer = self.query_one(AppFooter)

            # Show/hide main content panels
            dashboard.display = not selecting
            task_table.display = not selecting
            plan_table.display = selecting

            # Update footer and set focus
            if selecting: # Switching TO plan selection
                self.app_logger.info("Switching to plan selection view.")
                # Populate the table *before* trying to focus it
                self._populate_plan_selection_table()
                # Now focus the table, let Textual handle default cursor position (usually row 0)
                plan_table.focus()
            else:
                task_table = self.query_one("#task-table", DataTable)
                # Restore normal footer info (implementation needed in AppFooter)
                self.app_logger.info("Footer update needed for normal mode")
                # footer.update_info() # Example: Restore normal info
                task_table.focus()

        except Exception as e:
            self.app_logger.error(f"Error updating UI for plan selection state: {e}", exc_info=True)
            # Ensure focus goes somewhere safe if UI update fails
            try:
                self.query_one("#task-table").focus()
            except Exception:
                pass # Ignore if task table itself is the problem

    # --- New method to populate plan selection table ---
    def _populate_plan_selection_table(self) -> None:
        table = self.query_one("#plan-selection-table", DataTable)
        table.clear()
        base_dir = Path.cwd()
        for plan_path, project_data in self.all_plans.items():
            relative_path_str = str(plan_path.relative_to(base_dir) if plan_path.is_relative_to(base_dir) else plan_path)
            is_focus = project_data.focus if project_data else False
            focus_indicator = Text.from_markup("[b]>[/b]") if is_focus else Text(" ")

            if project_data is None:
                # Handle load error - Use Text.from_markup
                plan_name = Text.from_markup("[i red]Load Error[/i]") # Use Text object
            else:
                plan_name = project_data.project.name

            table.add_row(
                focus_indicator,
                plan_name, # This will now be a Text object in case of error
                relative_path_str,
                str(plan_path.resolve()),
                key=str(plan_path.resolve()) # Use full path as key
            )

    # --- Modified switch_focus_plan ---
    def switch_focus_plan(self, target_path: Path) -> None:
        """Switches the focus to the specified plan path and updates UI."""
        if not target_path or not target_path.exists():
            self.app_logger.error(
                f"Attempted to switch to non-existent plan: {target_path}"
            )
            self.notify(
                f"Cannot switch: Plan {target_path} not found.", severity="error"
            )
            return

        # Check if the target plan actually exists in our loaded plans
        if target_path not in self.all_plans:
            self.app_logger.warning(
                f"Attempted to switch to plan not in loaded list: {target_path}. Reloading might be needed."
            )
            # Optionally, you could try loading it here, but for now, just notify
            # self.all_plans.update(load_plans([target_path])) # Example: Force load attempt
            self.notify(
                f"Cannot switch: Plan {target_path.name} not loaded.",
                severity="warning",
            )
            return

        current_focus = self.current_plan_path
        if current_focus == target_path:
            self.app_logger.info(
                f"Already focused on {target_path.name}. No switch needed."
            )
            # Still need to exit selection mode if called from there
            if self.selecting_plan:
                self.app_logger.debug("Exiting selection mode after selecting the current plan.")
                self.selecting_plan = False
            return

        self.app_logger.info(
            f"Attempting to switch focus from {current_focus} to {target_path}"
        )

        try:
            # Manage focus handles the logic of setting 'focus: false' on the old plan
            # and 'focus: true' on the new one, then saving them.
            updated_plans, new_focus_path = manage_focus(
                self.all_plans, new_focus_target=target_path
            )

            # Update the internal state AFTER manage_focus has potentially saved files
            self.all_plans = updated_plans
            self.current_plan_path = new_focus_path # Should be == target_path if successful

            if self.current_plan_path == target_path:
                self.app_logger.info(f"Successfully switched focus to {target_path.name}")
                self.notify(f"Switched to plan: {target_path.name}")
                self.update_ui() # Update the UI to reflect the new plan
                self.selecting_plan = False # Exit selection mode after successful switch
            else:
                # This might happen if manage_focus failed to set the focus for some reason
                self.app_logger.error(f"Focus switch failed. Expected {target_path}, but got {self.current_plan_path}")
                self.notify(f"Failed to switch focus to {target_path.name}", severity="error")
                # Optionally, try to revert or handle the error state
                # For now, the UI might be out of sync or show the previous plan

        except Exception as e:
            self.app_logger.exception(f"Error switching focus to {target_path.name}")
            self.notify(f"Error switching plan: {e}", severity="error")

    # --- Actions for Plan Switching (Left/Right Arrows) ---
    def action_previous_plan(self) -> None:
        """Switches focus to the previous plan file in the sorted list."""
        # Only allow direct switching if NOT in plan selection mode
        if self.selecting_plan:
            self.app_logger.info("Ignoring Prev Plan action while in selection mode.")
            return
        self.app_logger.info("Action: Previous Plan")
        valid_plan_paths = sorted(
            [p for p, plan in self.all_plans.items() if plan is not None]
        )

        if len(valid_plan_paths) <= 1:
            self.notify("No previous plan to switch to.")
            return

        if self.current_plan_path is None:
            # If no current focus, maybe switch to the last one? Or first? Let's pick last.
            target_path = valid_plan_paths[-1]
            self.app_logger.info("No current focus, attempting to switch to last plan.")
        else:
            try:
                current_index = valid_plan_paths.index(self.current_plan_path)
                prev_index = (current_index - 1) % len(valid_plan_paths)  # Wrap around
                target_path = valid_plan_paths[prev_index]
            except ValueError:
                self.app_logger.warning(
                    f"Current focus path {self.current_plan_path} not found in valid paths. Switching to first."
                )
                target_path = valid_plan_paths[
                    0
                ]  # Default to first if current is somehow invalid

        self.switch_focus_plan(target_path)

    def action_next_plan(self) -> None:
        """Switches focus to the next plan file in the sorted list."""
        # Only allow direct switching if NOT in plan selection mode
        if self.selecting_plan:
            self.app_logger.info("Ignoring Next Plan action while in selection mode.")
            return
        self.app_logger.info("Action: Next Plan")
        valid_plan_paths = sorted(
            [p for p, plan in self.all_plans.items() if plan is not None]
        )

        if len(valid_plan_paths) <= 1:
            self.notify("No next plan to switch to.")
            return

        if self.current_plan_path is None:
            # If no current focus, maybe switch to the first one?
            target_path = valid_plan_paths[0]
            self.app_logger.info(
                "No current focus, attempting to switch to first plan."
            )
        else:
            try:
                current_index = valid_plan_paths.index(self.current_plan_path)
                next_index = (current_index + 1) % len(valid_plan_paths)  # Wrap around
                target_path = valid_plan_paths[next_index]
            except ValueError:
                self.app_logger.warning(
                    f"Current focus path {self.current_plan_path} not found in valid paths. Switching to first."
                )
                target_path = valid_plan_paths[
                    0
                ]  # Default to first if current is somehow invalid

        self.switch_focus_plan(target_path)

    # --- New/Modified on_key handler --- 
    async def on_key(self, event: events.Key) -> None:
        """Handle key presses, especially for plan selection mode."""
        # Log all key presses for debugging
        self.app_logger.debug(f"Key pressed: {event.key}, Selecting Plan: {self.selecting_plan}")

        if self.selecting_plan:
            if event.key == "enter":
                event.stop() # Prevent other handlers from processing Enter
                self.app_logger.info("Enter pressed in plan selection mode.")
                try:
                    table = self.query_one("#plan-selection-table", DataTable)
                    # Log focus status
                    self.app_logger.debug(f"Plan table focused: {table.has_focus}, App focused: {self.focused}")
                    # --- Corrected condition --- 
                    if table.cursor_row is not None:
                        # --- Changed back AGAIN to get_row_at --- 
                        row_data = table.get_row_at(table.cursor_row)
                        self.app_logger.debug(f"get_row_at returned: {row_data!r} (Type: {type(row_data)})" )
                        
                        key_string = None
                        if isinstance(row_data, (list, tuple)) and len(row_data) > 3: # Assuming key is 4th element (index 3)
                             key_string = row_data[3] 
                             if not isinstance(key_string, str):
                                 self.app_logger.error(f"Extracted key from row_data is not a string: {key_string!r}")
                                 key_string = None # Treat as failure
                        else:
                             self.app_logger.error(f"Could not extract key string from row_data: {row_data!r}")

                        if key_string: # Check if we got a valid string key
                            selected_path = Path(key_string)
                            if self.all_plans.get(selected_path) is not None:
                                self.app_logger.info(f"Attempting switch via Enter to: {selected_path}")
                                self.switch_focus_plan(selected_path)
                            else:
                                self.app_logger.warning(f"Enter selected invalid plan: {selected_path}")
                                self.notify(f"Cannot select plan '{selected_path.name}' due to loading error.", severity="error")
                        else:
                            self.app_logger.error("Could not get row key for Enter selection.")
                    else:
                         self.app_logger.warning("Enter pressed with no valid row selected in plan table.")
                except Exception as e:
                     self.app_logger.error(f"Error processing Enter in plan selection: {e}", exc_info=True)

            elif event.key == "escape":
                event.stop() # Prevent other handlers from processing Escape
                self.app_logger.info("Escape pressed in plan selection mode. Exiting selection.")
                self.selecting_plan = False # This will trigger watch and focus task table
            
        # If not selecting_plan, or key was not handled above, 
        # let the default key handling occur (e.g., for app-level bindings like Ctrl+C)

    # --- Modified initial load --- 
    def _initial_load_and_focus(self) -> None:
        """Loads initial plan files and determines the focus plan."""
        self.app_logger.info("Performing initial load and focus management...")
        try:
            # Ensure core imports are available if not already module level
            # from ..core import load_plans, manage_focus
            # from datetime import datetime

            loaded_plans = load_plans(self.initial_plan_files)
            # --- Debug Logging Start ---
            log_loaded_plans = {str(p): ("Project" if plan else "None") for p, plan in loaded_plans.items()}
            self.app_logger.debug(f"_initial_load_and_focus: load_plans result: {log_loaded_plans}")

            # manage_focus might save files if focus needs correction
            updated_plans, focus_path = manage_focus(loaded_plans)

            self.app_logger.debug(f"_initial_load_and_focus: manage_focus returned focus_path: {focus_path}")

            self.all_plans = updated_plans  # Update reactive variable
            self.current_plan_path = focus_path  # Update reactive variable
            self.last_load_time = datetime.now()

            self.app_logger.debug(f"_initial_load_and_focus: Set self.current_plan_path to: {self.current_plan_path}")
            # --- Debug Logging End ---

            if self.current_plan_path is None and any(
                updated_plans.values()
            ):  # Check if focus is None but plans exist
                self.app_logger.error(
                    "Failed to determine a focus plan during initial load, although valid plans exist."
                )
                # Display an error message in the UI? Maybe ProjectInfo?
                # The update_ui call below will handle displaying an error state
                self.notify(
                    "Error: Could not set focus plan.",
                    title="Load Error",
                    severity="error",
                )
            elif self.current_plan_path is None:
                self.app_logger.warning("No valid plans loaded or found.")
                self.notify(
                    "No valid plan files found or loaded.",
                    title="Load Warning",
                    severity="warning",
                )

            self.update_ui()  # Update UI with loaded data
            # Update footer initially
            try:
                footer = self.query_one(AppFooter)
                footer.current_plan_path = self.current_plan_path
                footer.update_info()  # Update with time and initial plan
            except Exception as e:
                self.app_logger.error(f"Error setting initial footer info: {e}")

            self.app_logger.info("Initial load and focus management complete.")

        except Exception as e:
            self.app_logger.exception(
                "Critical error during initial load and focus management."
            )
            # Display error to user
            self.notify(
                f"Critical error loading plans: {e}",
                title="Load Error",
                severity="error",
                timeout=10,
            )
            # Set state to indicate error
            self.all_plans = {}
            self.current_plan_path = None
            self.update_ui()  # Try to update UI to show empty state/error


# Note: The part that runs the app (`if __name__ == "__main__":`) is NOT copied here.
# It will be handled by the CLI entry point (Task 11). 
