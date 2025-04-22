# -*- coding: utf-8 -*-
"""Custom Textual widgets for the Metsuke TUI."""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple, Union
from collections import Counter
from pathlib import Path # Import Path

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, ProgressBar
from textual.reactive import reactive, var
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel

# Import Pydantic models from the core package
# Assuming models.py is one level up from tui directory
# Adjust relative path if needed
from ..models import ProjectMeta, Task # Import Task as well

# Import utility functions if needed (e.g., for colors)
# from ..utils import _get_status_color # Assuming utils exist or define locally

# --- UI Components --- Note: TypedDicts for data are now in models.py

# --- Title Widget ---
class TitleDisplay(Static):
    """A widget to display the application title."""

    title_text: reactive[str] = reactive("[b cyan]Metsuke[/]") # Default title
    author_name: str = "Liang,Yi <cidxb@github.com>" # Updated author name

    def render(self) -> Text:
        """Render the title and author with specific alignment."""
        width = self.size.width

        # Define the text components with styles
        # Using $accent for title, dim italic for author
        title = Text("Metsuke", style="b cyan")
        author = Text(f"by {self.author_name}", style="dim i")

        # Calculate padding
        title_len = len(title)
        author_len = len(author)

        if width < title_len + author_len + 1: # Not enough space
            # Just center the title if space is tight
            return Text("Metsuke", style="b cyan", justify="center")

        # Calculate padding for center/right alignment
        left_padding_len = (width - title_len) // 2
        mid_padding_len = width - left_padding_len - title_len - author_len

        # Assemble the final text
        return Text.assemble(
            (" " * left_padding_len), # Left padding for title centering
            title,
            (" " * mid_padding_len), # Middle padding
            author,
        )

    def update(self, new_title: str) -> None:
        """Update the displayed title."""
        self.title_text = new_title

# --- Project Info Widget ---
class ProjectInfo(Static):
    """Displays project metadata with enhanced styling."""

    # Removed reactive variables, state is now passed directly to _render_display

    # Modified _render_display to accept arguments directly
    def _render_display(self, project: Optional[ProjectMeta], plan_path: Optional[Path]) -> None:
        """Updates the renderable content based on current state."""
        # --- Debug Logging Start ---
        # Log the arguments passed in
        logging.getLogger(__name__).debug(f"_render_display called with: project={project!r}, plan_path={plan_path!r}")
        # --- Debug Logging End ---
        if project: # Use the passed argument
            try:
                # Display path relative to CWD if possible
                display_path = str(plan_path.relative_to(Path.cwd()))
            except (ValueError, AttributeError):
                # Fallback to just the filename or N/A
                display_path = plan_path.name if plan_path else "[i]N/A[/i]"

            # Use theme variable $accent for project name
            # Use dim or $text-muted for version and path
            name_style = "b cyan"
            version_style = ""
            path_style = "dim blue"
            license_style = "dim"

            # Construct line by line for better control
            # Avoid empty style tag if version_style is empty
            version_part = f"[{version_style}]{project.version}[/]" if version_style else project.version
            line1 = f"[{name_style}]{project.name}[/] ({version_part})"
            line2 = f"[{path_style}]{display_path}[/]"
            info_text = f"{line1}\n{line2}"
            if project.license: # Add license on a new line if present
                info_text += f"\n[{license_style}]License: {project.license}[/]"
            # Use Text object for centering
            logging.getLogger(__name__).debug(f"Generated info_text: {info_text!r}")
            self.update(Text.from_markup(info_text, justify="center"))
            logging.getLogger(__name__).debug("ProjectInfo update call completed within if.")
        else:
            # Handle error loading or no plan loaded
            error_text = "[b red]No Plan Loaded[/]"
            if plan_path: # Show path if available even on load error
                try:
                    display_path = str(plan_path.relative_to(Path.cwd()))
                except (ValueError, AttributeError):
                    display_path = plan_path.name
                error_text = f"[b red]Error loading:[/] [{path_style}]{display_path}[/]"
            # Use Text object for centering
            logging.getLogger(__name__).debug(f"Generated error_text: {error_text!r}")
            self.update(Text.from_markup(error_text, justify="center"))
            logging.getLogger(__name__).debug("ProjectInfo update call completed within else.")


class TaskProgress(Container):
    """Displays overall task progress with a bar."""

    progress_percent: var[float] = var(0.0)
    counts: var[Dict[str, int]] = var(Counter())

    # Helper to get status colors (can be moved to a utility module later)
    def _get_status_color(self, status: str) -> str:
        return {
            "Done": "green",       # Standard Rich color
            "in_progress": "yellow", # Standard Rich color
            "pending": "blue",       # Standard Rich color
            "blocked": "red",        # Standard Rich color
        }.get(status.lower(), "$text") # Default to standard text

    def compose(self) -> ComposeResult:
        yield Static("", id="progress-text")
        yield ProgressBar(total=100.0, show_eta=False, id="overall-progress-bar")

    def update_progress(self, counts: Dict[str, int], progress_percent: float) -> None:
        logging.getLogger(__name__).info(f"TaskProgress received counts: {counts}, progress: {progress_percent:.1f}%")
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
            f"Blocked: [red]{blocked}[/]")
        progress_text = f"[b bright_white]Tasks Progress:[/]{done}/{total} ({self.progress_percent:.1f}%)"
        self.query_one("#progress-text", Static).update(f"{progress_text}\n{status_line}")
        self.query_one(ProgressBar).update(progress=self.progress_percent)


class PriorityBreakdown(Static):
    """Displays task count by priority."""

    priority_counts: var[Dict[str, int]] = var(Counter())

    def render(self) -> str:
        lines = ["[b bright_white]Priority Breakdown:[/]", "--- "] # Added separator
        high = self.priority_counts.get("high", 0)
        medium = self.priority_counts.get("medium", 0)
        low = self.priority_counts.get("low", 0)
        lines.append(f"• High priority: [red]{high}[/]")
        lines.append(f"• Medium priority: [yellow]{medium}[/]")
        lines.append(f"• Low priority: [green]{low}[/]")
        return "\n".join(lines)


class DependencyStatus(Static):
    """Displays dependency metrics and next task suggestion."""

    metrics: var[Dict[str, Any]] = var({}) # Holds calculated metrics
    # Removed direct task_list var

    # Helper to get priority colors (can be moved later)
    def _get_priority_color(self, priority: str) -> str:
        return {
            "high": "red",    # Standard Rich color
            "medium": "yellow", # Standard Rich color
            "low": "green",   # Standard Rich color
        }.get(priority.lower(), "$text")

    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """Updates the widget with pre-calculated dependency metrics."""
        logging.getLogger(__name__).info(f"DependencyStatus received metrics: {metrics}")
        self.metrics = metrics
        self.refresh()

    def render(self) -> str:
        lines = ["[b bright_white]Dependency Status & Next Task[/]", "--- "] # Added separator
        lines.append("[u bright_white]Dependency Metrics:[/]")
        lines.append(f"• Tasks with no dependencies: {self.metrics.get('no_deps', 0)}")
        lines.append(f"• Tasks ready to work on: {self.metrics.get('ready_to_work', 0)}")
        lines.append(f"• Tasks blocked by dependencies: {self.metrics.get('blocked_by_deps', 0)}")
        if self.metrics.get("most_depended_id") is not None:
            lines.append(
                f"• Most depended-on task: #{self.metrics['most_depended_id']} ({self.metrics['most_depended_count']} dependents)")
        lines.append(
            f"• Avg dependencies per task: {self.metrics.get('avg_deps', 0.0):.1f}")

        lines.append("\n[u bright_white]Next Task to Work On:[/]")
        next_task = self.metrics.get("next_task")
        if next_task and isinstance(next_task, Task): # Check if it's a Task object
            lines.append(f"[b]ID:[/b] #{next_task.id} ([b]{next_task.title}[/])")
            priority_color = {"high": "red", "medium": "yellow", "low": "green"}.get(next_task.priority, "white")
            lines.append(f"[b]Priority:[/b] [{priority_color}]{next_task.priority}[/]")
            deps = ", ".join(map(str, next_task.dependencies)) or "None"
            lines.append(f"[b]Dependencies:[/b] {deps}")
        else:
            lines.append("[i]ID: N/A - No task available[/i]")

        return "\n".join(lines)


# --- New Custom Footer ---
class AppFooter(Container):
    """A custom footer that displays bindings and dynamic info."""

    # Add state for the current plan path
    current_plan_path: var[Optional[Path]] = var(None)

    DEFAULT_CSS = """
    /* Using App CSS for layout */
    AppFooter > #footer-bindings {
        color: $text-muted;
    }
    AppFooter > #footer-info {
        color: $text-muted;
    }
    """

    def __init__(self, bindings: List[Any], **kwargs):
        super().__init__(**kwargs)
        # Store only the relevant parts for display (key, description)
        self._bindings_data = []
        for item in bindings:
             # Handle Binding objects
             if isinstance(item, Binding):
                  if item.show: # Only process bindings marked to be shown
                       key_display = item.key_display if item.key_display else item.key
                       self._bindings_data.append((key_display, item.description))
             # Handle tuple format (assuming 3 elements: key, action, description)
             elif isinstance(item, tuple) and len(item) == 3:
                  key, _, desc = item
                  # Assuming all tuples passed are meant to be shown
                  self._bindings_data.append((key, desc))
             # Optional: Log or ignore other types
             # else:
             #    self.log.warning(f"Ignoring unknown item type in AppFooter bindings: {type(item)}")

    def compose(self) -> ComposeResult:
        yield Static(id="footer-bindings")
        yield Static(id="footer-info")

    def on_mount(self) -> None:
        """Called when the footer is mounted."""
        self._update_bindings()
        self.update_info() # Initial update
        self.set_interval(1, self.update_info) # Update info every second

    def _update_bindings(self) -> None:
        """Formats and displays the key bindings."""
        b = self.query_one("#footer-bindings", Static)
        # Format bindings similar to Textual's default Footer
        bindings_text = " | ".join(f"[dim]{key}[/]:{desc}" for key, desc in self._bindings_data if desc) # Filter out bindings without description if necessary
        b.update(bindings_text)

    # Rename to update_info to match app.py call
    def update_info(self) -> None:
        """Updates the time and current plan path information."""
        info_widget = self.query_one("#footer-info", Static)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Display current plan path
        plan_str = "Plan: N/A"
        if self.current_plan_path:
            try:
                # Try to show relative path for brevity
                plan_str = f"Plan: {self.current_plan_path.relative_to(Path.cwd())}"
            except ValueError:
                plan_str = f"Plan: {self.current_plan_path.name}"

        # Combine time and plan path
        info_text = f"{now_str} | {plan_str}"
        info_widget.update(info_text) 

    # Add watch method for the new reactive variable
    def watch_current_plan_path(self, new_path: Optional[Path]) -> None:
         self.update_info() # Trigger update when path changes 