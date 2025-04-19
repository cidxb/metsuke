#!/usr/bin/env python
"""
Metsuke TUI - A Terminal UI for viewing PROJECT_PLAN.yaml.

Usage:
  1. Install dependencies: pip install textual pyyaml watchdog pyperclip
  2. Run the script: python task_viewer.py

The TUI will automatically update when PROJECT_PLAN.yaml is modified.
"""

import yaml
import threading  # Added for watchdog observer
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, TypedDict
from collections import Counter, deque # Import deque
# import logging # Removed old import

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
# from textual.widgets import Header, Footer, Static, DataTable, ProgressBar # Footer removed
from textual.widgets import Header, Static, DataTable, ProgressBar, Log, Markdown, Footer # Added Log, removed Footer
from textual.reactive import var
from textual.screen import ModalScreen

# Watchdog imports
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Re-import logging for TUI handler
import logging
import pyperclip # Import pyperclip

PLAN_FILE = Path("PROJECT_PLAN.yaml")

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
            self.log_widget.write(msg)
            self.messages.append(msg) # Also store the message
        except Exception:
            self.handleError(record)

# --- Watchdog Event Handler ---


class PlanFileEventHandler(FileSystemEventHandler):
    """Handles file system events for PROJECT_PLAN.yaml."""

    def __init__(self, app: App, file_path: Path):
        self.app = app
        self.file_path = file_path.resolve()  # Get absolute path

    def on_modified(self, event):
        """Called when a file or directory is modified."""
        # Check if the modified file is the one we are watching
        # event.src_path gives the path of the modified item
        if not event.is_directory and Path(event.src_path).resolve() == self.file_path:
            self.app.log(f"Watchdog detected modification in {self.file_path}")
            # Safely call the app's reload method from the watchdog thread
            self.app.call_from_thread(self.app.reload_plan_data)


# Define data structures for type hinting
class ProjectMeta(TypedDict):
    name: str
    version: str


class Task(TypedDict):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    dependencies: List[int]


class PlanData(TypedDict):
    project: ProjectMeta
    tasks: List[Task]


# --- UI Components ---


class TitleDisplay(Static):
    """Displays the main title."""

    def render(self) -> str:
        # Basic text title, ASCII art is harder to manage dynamically
        # return "[b cyan]TaskMaster[/]" # Old name
        return "[b cyan]Metsuke[/]" # New name


class ProjectInfo(Static):
    """Displays project metadata."""

    meta: var[Optional[ProjectMeta]] = var(None)

    def watch_meta(self, meta: Optional[ProjectMeta]) -> None:
        if meta:
            # Displaying like the box in the image
            self.update(
                f"Version: [b]{meta['version']}[/] Project: [b]{meta['name']}[/]"
            )
        else:
            self.update("Version: N/A Project: N/A")


# Modified TaskProgress to be a Container with ProgressBar
class TaskProgress(Container):
    """Displays overall task progress with a bar."""

    progress_percent: var[float] = var(0.0)
    counts: var[Dict[str, int]] = var(Counter())

    def compose(self) -> ComposeResult:
        yield Static("", id="progress-text")
        yield ProgressBar(total=100.0, show_eta=False, id="overall-progress-bar")

    def update_progress(self, counts: Dict[str, int], progress_percent: float) -> None:
        # self.log(f"TaskProgress received counts: {counts}, progress_percent: {progress_percent}") # Re-add log
        logging.getLogger(__name__).info(f"TaskProgress received counts: {counts}, progress: {progress_percent:.1f}%") # Use standard logger
        self.counts = counts
        self.progress_percent = progress_percent

        total = sum(self.counts.values())
        if not total:
            self.query_one("#progress-text", Static).update("No tasks found.")
            self.query_one(ProgressBar).update(progress=0)
            return

        done = self.counts.get("Done", 0)
        in_progress = self.counts.get("in_progress", 0)
        pending = self.counts.get("pending", 0)
        blocked = self.counts.get("blocked", 0)

        status_line = (
            f"Done: [green]{done}[/] | "
            f"In Progress: [yellow]{in_progress}[/] | "
            f"Pending: [blue]{pending}[/] | "
            f"Blocked: [red]{blocked}[/]"
        )
        progress_text = f"[b bright_white]Tasks Progress:[/]{done}/{total} ({self.progress_percent:.1f}%)"
        self.query_one("#progress-text", Static).update(f"{progress_text}\n{status_line}")
        self.query_one(ProgressBar).update(progress=self.progress_percent)

    # Removed render method


class PriorityBreakdown(Static):
    """Displays task count by priority."""

    priority_counts: var[Dict[str, int]] = var(Counter())

    def render(self) -> str:
        lines = ["[b bright_white]Priority Breakdown:[/]"]
        high = self.priority_counts.get("high", 0)
        medium = self.priority_counts.get("medium", 0)
        low = self.priority_counts.get("low", 0)
        lines.append(f"• High priority: [red]{high}[/]")
        lines.append(f"• Medium priority: [yellow]{medium}[/]")
        lines.append(f"• Low priority: [green]{low}[/]")
        return "\n".join(lines)


class DependencyStatus(Static):
    """Displays dependency metrics and next task suggestion."""

    metrics: var[Dict[str, Any]] = var({})

    def render(self) -> str:
        # self.log(f"DependencyStatus rendering with metrics: {self.metrics}") # Re-add log
        logging.getLogger(__name__).info(f"DependencyStatus rendering with metrics: {self.metrics}") # Use standard logger
        lines = ["[b bright_white]Dependency Status & Next Task[/]"]
        lines.append("[u bright_white]Dependency Metrics:[/]")
        lines.append(f"• Tasks with no dependencies: {self.metrics.get('no_deps', 0)}")
        lines.append(
            f"• Tasks ready to work on: {self.metrics.get('ready_to_work', 0)}"
        )
        lines.append(
            f"• Tasks blocked by dependencies: {self.metrics.get('blocked_by_deps', 0)}"
        )
        if self.metrics.get("most_depended_id") is not None:
            lines.append(
                f"• Most depended-on task: #{self.metrics['most_depended_id']} ({self.metrics['most_depended_count']} dependents)"
            )
        lines.append(
            f"• Avg dependencies per task: {self.metrics.get('avg_deps', 0.0):.1f}"
        )

        lines.append("\n[u bright_white]Next Task to Work On:[/]")
        next_task = self.metrics.get("next_task")
        if next_task:
            lines.append(f"[b]ID:[/b] #{next_task['id']} ([b]{next_task['title']}[/])")
            priority_color = {"high": "red", "medium": "yellow", "low": "green"}.get(next_task['priority'], "white")
            lines.append(f"[b]Priority:[/b] [{priority_color}]{next_task['priority']}[/]")
            deps = ", ".join(map(str, next_task["dependencies"])) or "None"
            lines.append(f"[b]Dependencies:[/b] {deps}")
        else:
            lines.append("[i]ID: N/A - No task available[/i]")

        return "\n".join(lines)


# New StatusBar Widget
class StatusBar(Static):
    """Displays clock and author info at the bottom."""
    def on_mount(self) -> None:
        """Start the timer."""
        self.update_time()
        self.set_interval(1, self.update_time)

    def update_time(self) -> None:
        """Update the time and author display."""
        now = datetime.now().strftime("%H:%M:%S") # Use only time for less clutter
        author = "Author: Liang,Yi @ https://github.com/cidxb"
        # Attempt approximate centering of time
        width = self.size.width
        time_len = len(now)
        author_len = len(author)
        space_len = width - time_len - author_len
        left_pad = space_len // 2
        right_pad = space_len - left_pad
        if space_len < 1:
            # If not enough space, just show time and author truncated if needed
            self.update(f"{now} {author[:width-time_len-1]}")
        else:
            self.update(f"{' '*left_pad}{now}{' '*right_pad}{author}")


# Re-add HelpScreen Widget
class HelpScreen(ModalScreen):
    """Modal screen to display help and context."""

    CSS = """
    HelpScreen {
        align: center middle;
        /* background: rgba(0, 0, 0, 0.5); */ /* Temporarily removed for testing border issue */
    }
    HelpScreen > Container {
        /* width: auto; */ /* Changed from auto */
        width: 75%; /* Set a fixed percentage width */
        max-width: 90%; /* Keep max width */
        max-height: 90%;
        /* min-width: 60%; */ /* Remove min-width as width is now fixed */
        /* border: thick $accent; */ /* Changed border style */
        border: round $accent; /* Use round border for better compatibility */
        background: $surface; /* Background for the box itself */
        padding: 1 2;
    }
    HelpScreen .title { width: 100%; text-align: center; margin-bottom: 1; }
    HelpScreen .context { margin-bottom: 1; border: round $accent-lighten-1; padding: 1; max-height: 25; overflow-y: auto; }
    HelpScreen .bindings { margin-bottom: 1; border: round $accent-lighten-1; padding: 1; }
    HelpScreen .close-hint { width: 100%; text-align: center; margin-top: 1; color: $text-muted; }
    """

    BINDINGS = [
        ("escape,q", "close_help", "Close"),
        ("ctrl+l", "copy_log", "Copy Log"),
        ("ctrl+d", "toggle_log", "Toggle Log"),
        ("ctrl+p", "open_command_palette", "Open Command Palette"),
        ("?", "show_help", "Help")
    ]

    def __init__(self, plan_context: str):
        super().__init__()
        self.plan_context = plan_context

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("[b]Help / Context[/b]", classes="title")
            yield Markdown(self.plan_context or "_No context provided in PROJECT_PLAN.yaml_", classes="context")
            yield Static("[u]Key Bindings:[/u]\n"
                         " Q / Esc : Close Help / Quit App\n"
                         " Ctrl+L  : Copy Log to Clipboard\n"
                         " Ctrl+D  : Toggle Log Panel Visibility\n"
                         " Ctrl+P  : Open Command Palette (theme, etc.)\n"
                         " ?       : Show this Help Screen", classes="bindings")
            yield Static("Press Esc or Q to close.", classes="close-hint")

    def action_close_help(self) -> None:
        self.app.pop_screen()


# --- Main App ---


class TaskViewer(App):
    """A Textual app to view project tasks from PROJECT_PLAN.yaml."""

    # CSS_PATH = "task_viewer.css" # Already commented out
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+l", "copy_log", "Copy Log"),
        ("ctrl+d", "toggle_log", "Toggle Log"),
        ("?", "show_help", "Help")
    ]

    plan_data: var[Optional[PlanData]] = var(None, init=False)
    plan_context: var[str] = var("") # Re-add variable for context
    last_load_time: var[Optional[datetime]] = var(None, init=False)
    observer: var[Optional[Observer]] = var(None, init=False)  # Store observer

    # Class logger for the App itself
    app_logger = logging.getLogger("TaskViewerApp")

    def __init__(self):
        super().__init__()
        self._load_data()  # Load data on initialization

    def compose(self) -> ComposeResult:
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
        yield StatusBar(id="status-bar") # Add StatusBar
        yield Log(id="log-view", max_lines=200, highlight=True)
        yield Footer() # Add Footer

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Setup TUI logging handler
        log_widget = self.query_one(Log)
        tui_handler = TuiLogHandler(log_widget)
        # Configure format for TUI handler - ADD NEWLINE \n AT THE END
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s: %(message)s\n', datefmt='%H:%M:%S')
        tui_handler.setFormatter(formatter)
        # Store handler for copy action
        self.tui_handler = tui_handler

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # Clear existing handlers if any to avoid duplicates if app restarts
        # root_logger.handlers.clear() # Be careful with this in complex setups
        root_logger.addHandler(self.tui_handler)
        root_logger.propagate = False

        self.app_logger.info("TUI Log Handler configured. Press Ctrl+L to copy log.")

        self.update_ui()
        self.start_file_observer()
        self.query_one(DataTable).focus()

    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        self.stop_file_observer()  # Stop watchdog observer

    def start_file_observer(self) -> None:
        """Starts the watchdog file observer."""
        if not PLAN_FILE.exists():
            self.log.warning(f"Cannot watch {PLAN_FILE} - file does not exist.")
            return

        event_handler = PlanFileEventHandler(self, PLAN_FILE)
        self.observer = Observer()
        # Watch the directory containing the file for better reliability
        watch_path = str(PLAN_FILE.parent.resolve())
        self.observer.schedule(event_handler, watch_path, recursive=False)
        self.observer.daemon = (
            True  # Allow app to exit even if observer thread is running
        )
        self.observer.start()
        self.log(f"Started watching {watch_path} for changes to {PLAN_FILE.name}")

    def stop_file_observer(self) -> None:
        """Stops the watchdog file observer."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()  # Wait for the thread to finish
            self.log("Stopped file observer.")
        self.observer = None

    def reload_plan_data(self) -> None:
        """Reloads data and updates UI (called from watchdog thread via call_from_thread)."""
        self.app_logger.info("Reloading plan data due to file change...") # Use logger
        self._load_data()
        self.update_ui()

    def _load_data(self) -> None:
        """Loads data from the YAML file."""
        try:
            if PLAN_FILE.exists():
                with open(PLAN_FILE, "r") as f:
                    data = yaml.safe_load(f)
                    if data and "project" in data and "tasks" in data:
                        self.plan_data = data
                        # Re-add context loading
                        self.plan_context = data.get('context', '')
                        self.last_load_time = datetime.now()
                        self.app_logger.info("Plan data loaded successfully.") # Use logger
                    else:
                        self.app_logger.error("Invalid YAML structure.") # Use logger
                        self.plan_data = None
                        self.plan_context = "" # Clear context on error
            else:
                self.app_logger.warning(f"{PLAN_FILE} not found.") # Use logger
                self.plan_data = None
                self.plan_context = "" # Clear context if file not found
        except FileNotFoundError:
            self.app_logger.error(f"{PLAN_FILE} not found during load attempt.") # Use logger
            self.plan_data = None
            self.plan_context = ""
        except yaml.YAMLError as e:
            self.app_logger.error(f"Error parsing {PLAN_FILE}: {e}") # Use logger
            self.plan_data = None
            self.plan_context = ""
        except Exception as e:
            self.app_logger.error(f"Unexpected error loading data: {e}") # Use logger
            self.plan_data = None
            self.plan_context = ""

    def update_ui(self) -> None:
        """Updates all UI components with the latest data."""
        self.app_logger.info("Updating UI...") # Log UI update start
        if not self.plan_data:
            self.app_logger.warning("No plan data found, clearing UI.") # Log clearing
            self.query_one(ProjectInfo).meta = None
            table = self.query_one(DataTable)
            table.clear(columns=True)
            table.add_columns("ID", "Title", "Status", "Priority", "Dependencies")
            table.add_row("[i]No data loaded. Check PROJECT_PLAN.yaml[/i]", span=5)
            self.title = "TaskMaster - Error"
            # Clear stats
            try:
                tp = self.query_one(TaskProgress)
                tp.update_progress(Counter(), 0.0)
                # tp.refresh() # Removed container refresh
                self.query_one("#progress-text", Static).refresh() # Refresh child static
                pb = self.query_one(PriorityBreakdown)
                pb.priority_counts = Counter()
                pb.refresh()
                ds = self.query_one(DependencyStatus)
                ds.metrics = {}
                ds.refresh()
            except Exception:
                pass  # Widgets might not exist yet if data load failed early
            return

        project_meta = self.plan_data.get("project")
        tasks = self.plan_data.get("tasks", [])

        # Update App Title (now set in App __init__ or can be dynamic)
        # self.title = f"TaskMaster - {project_meta.get('name', 'N/A')}" # Already dynamic via ProjectInfo?
        # Let's keep the main title static for now

        # Update Project Info Widget
        self.query_one(ProjectInfo).meta = project_meta

        # Update Task Table
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Title", "Status", "Priority", "Dependencies")
        table.fixed_columns = 1  # Keep ID column fixed
        table.cursor_type = "row"
        for task in tasks:
            deps_str = ", ".join(map(str, task.get("dependencies", []))) or "None"
            status = task.get("status", "unknown")
            priority = task.get("priority", "unknown")
            status_styled = f"[{self._get_status_color(status)}]{status}[/]"
            priority_styled = f"[{self._get_priority_color(priority)}]{priority}[/]"
            table.add_row(
                str(task.get("id", "")),
                task.get("title", "No Title"),
                status_styled,
                priority_styled,
                deps_str,
                key=str(task.get("id")),  # Add key for cursor interaction
            )

        # Calculate and Update Stats
        if tasks:
            total_tasks = len(tasks)
            status_counts = Counter(t["status"] for t in tasks)
            priority_counts = Counter(t["priority"] for t in tasks)
            done_count = status_counts.get("Done", 0)
            progress_percent = (
                (done_count / total_tasks) * 100 if total_tasks > 0 else 0
            )
            # Log calculated stats (using app logger)
            self.app_logger.info(f"Calculated status_counts: {status_counts}")
            self.app_logger.info(f"Calculated progress_percent: {progress_percent:.1f}%")
            self.app_logger.info(f"Calculated priority_counts: {priority_counts}")

            # Update Task Progress Widget
            tp = self.query_one(TaskProgress)
            tp.update_progress(status_counts, progress_percent)
            self.query_one("#progress-text", Static).refresh()

            # Update Priority Breakdown Widget
            pb = self.query_one(PriorityBreakdown)
            pb.priority_counts = priority_counts
            pb.refresh()

            # Calculate Dependency Metrics
            dep_metrics = self._calculate_dependency_metrics(tasks)
            self.app_logger.info(f"Calculated dep_metrics: {dep_metrics}") # Log metrics
            ds = self.query_one(DependencyStatus)
            ds.metrics = dep_metrics
            ds.refresh()
        else:
            # Clear stats if no tasks
            self.app_logger.info("Clearing statistics as no tasks found.") # Log clearing
            tp = self.query_one(TaskProgress)
            tp.update_progress(Counter(), 0.0)
            self.query_one("#progress-text", Static).refresh()
            pb = self.query_one(PriorityBreakdown)
            pb.priority_counts = Counter()
            pb.refresh()
            ds = self.query_one(DependencyStatus)
            ds.metrics = {}
            ds.refresh()

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

    def _calculate_dependency_metrics(self, tasks: List[Task]) -> Dict[str, Any]:
        if not tasks:
            return {}

        task_map = {t["id"]: t for t in tasks}
        done_ids = {t["id"] for t in tasks if t["status"] == "Done"}
        dependents_count = Counter()
        total_deps = 0
        no_deps_count = 0
        blocked_by_deps_count = 0
        ready_tasks = []

        for task in tasks:
            deps = task.get("dependencies", [])
            total_deps += len(deps)
            if not deps:
                no_deps_count += 1

            is_blocked = False
            for dep_id in deps:
                dependents_count[dep_id] += 1
                if dep_id not in done_ids:
                    is_blocked = True

            if task["status"] != "Done":
                if is_blocked:
                    blocked_by_deps_count += 1
                else:
                    ready_tasks.append(task)

        most_depended = dependents_count.most_common(1)
        most_depended_id = most_depended[0][0] if most_depended else None
        most_depended_count = most_depended[0][1] if most_depended else 0

        next_task = None
        if ready_tasks:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            ready_tasks.sort(
                key=lambda t: (priority_order.get(t["priority"], 99), t["id"])
            )
            next_task = ready_tasks[0]

        return {
            "no_deps": no_deps_count,
            "ready_to_work": len(ready_tasks),
            "blocked_by_deps": blocked_by_deps_count,
            "most_depended_id": most_depended_id,
            "most_depended_count": most_depended_count,
            "avg_deps": total_deps / len(tasks) if tasks else 0.0,
            "next_task": next_task,
        }

    def action_copy_log(self) -> None:
        """Copies the current log content to the clipboard."""
        if hasattr(self, 'tui_handler') and self.tui_handler.messages:
            log_content = "\n".join(self.tui_handler.messages)
            try:
                pyperclip.copy(log_content)
                self.app_logger.info(f"{len(self.tui_handler.messages)} log lines copied to clipboard.")
            except Exception as e:
                # Log error to the TUI log itself
                self.app_logger.error(f"Failed to copy log to clipboard: {e}")
                # Also log to stderr in case the TUI logger fails
                # print(f"Error copying log: {e}", file=sys.stderr)
        elif hasattr(self, 'tui_handler'):
             self.app_logger.info("Log is empty, nothing to copy.")
        else:
            # This case should ideally not happen if on_mount ran correctly
            pass # Or log a warning that handler isn't ready

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
        self.push_screen(HelpScreen(plan_context=self.plan_context))


if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s') # Removed basicConfig

    TaskViewer.CSS = """
    Screen {
        background: $surface;
        color: $text;
        layout: vertical;
    }
    TitleDisplay {
        width: 100%;
        text-align: center;
        height: auto;
        margin-bottom: 1;
    }
    ProjectInfo {
        width: 100%;
        height: auto;
        border: thick $accent;
        padding: 0 1;
        text-align: center;
        /* margin-bottom: 1; */ /* Removed margin, handled by HeaderInfo */
    }
    /* Re-add Style for Header Info */
    HeaderInfo {
        height: 1;
        width: 100%;
        text-align: right;
        color: $text-muted;
        padding: 0 1;
        margin-bottom: 1; /* Add space below header */
    }
    Container#main-container { /* Style the main content area */
        height: 1fr;
    }
    #dashboard {
        height: auto;
        border: thick $accent;
        margin-bottom: 1;
    }
    #left-panel, #right-panel {
        width: 1fr;
        border: thick $accent;
        padding: 1;
        height: auto;
    }
    #task-table {
        height: 1fr;
        border: thick $accent;
    }
    /* Styles for widgets inside panels */
    TaskProgress {
        height: auto;
        margin-bottom: 1;
    }
    #progress-text {
        height: auto;
    }
    #overall-progress-bar {
        width: 100%;
        height: 1;
        margin-top: 1;
    }
    PriorityBreakdown, DependencyStatus {
        height: auto;
        margin-bottom: 1;
    }
    DataTable {
        height: auto; /* Let the container handle height */
    }
    /* --- Column Width Adjustments --- */
    # DataTable > .datatable--header > .column-key--id,
    # DataTable > .datatable--body > .datatable--row > .column-key--id {
    #     width: 5;
    #     text-align: center;
    # }
    # DataTable > .datatable--header > .column-key--status,
    # DataTable > .datatable--body > .datatable--row > .column-key--status {
    #     width: 15;
    #     text-align: center;
    # }
    # DataTable > .datatable--header > .column-key--priority,
    # DataTable > .datatable--body > .datatable--row > .column-key--priority {
    #     width: 12;
    #     text-align: center;
    # }
    # DataTable > .datatable--header > .column-key--dependencies,
    # DataTable > .datatable--body > .datatable--row > .column-key--dependencies {
    #     width: 15;
    #     text-align: center;
    # }
    # DataTable > .datatable--header > .column-key--title,
    # DataTable > .datatable--body > .datatable--row > .column-key--title {
    #     width: 1fr; /* Title takes remaining space */
    #     min-width: 40; /* Minimum width for Title */
    # }
    /* Add style for the Log widget if needed */
    Log {
        height: 8; /* Example height, adjust as needed */
        border-top: thick $accent;
        /* margin-top: 1; */ /* Add space above log if desired */
        display: none; /* Hide log by default */
    }
    /* Style for Author Info */
    #author-info {
        height: 1;
        text-align: right;
        color: $text-muted;
        margin: 0 1;
    }
    /* Re-add HelpScreen CSS */
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Container {
        width: auto;
        max-width: 80%;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    HelpScreen .title { width: 100%; text-align: center; margin-bottom: 1; }
    HelpScreen .context { margin-bottom: 1; border: round $accent-lighten-1; padding: 1; max-height: 25; overflow-y: auto; }
    HelpScreen .bindings { margin-bottom: 1; border: round $accent-lighten-1; padding: 1; }
    HelpScreen .close-hint { width: 100%; text-align: center; margin-top: 1; color: $text-muted; }
    """
    app = TaskViewer()
    app.run()
