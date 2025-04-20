# -*- coding: utf-8 -*-
"""Custom Textual widgets for the Metsuke TUI."""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List, Tuple
from collections import Counter

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, ProgressBar
from textual.reactive import var

# Import Pydantic models from the core package
# Assuming models.py is one level up from tui directory
# Adjust relative path if needed
from ..models import ProjectMeta, Task # Import Task as well


# --- UI Components --- Note: TypedDicts for data are now in models.py

class TitleDisplay(Static):
    """Displays the main title."""
    def render(self) -> str:
        return "[b cyan]Metsuke[/]"


class ProjectInfo(Static):
    """Displays project metadata."""

    meta: var[Optional[ProjectMeta]] = var(None)

    def watch_meta(self, meta: Optional[ProjectMeta]) -> None:
        if meta:
            # Use attribute access for Pydantic models
            self.update(
                f"Version: [b]{meta.version}[/] Project: [b]{meta.name}[/]{f' License: {meta.license}' if meta.license else ''}"
            )
        else:
            self.update("Version: N/A Project: N/A")


class TaskProgress(Container):
    """Displays overall task progress with a bar."""

    progress_percent: var[float] = var(0.0)
    counts: var[Dict[str, int]] = var(Counter())

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

    DEFAULT_CSS = """
    /* Using App CSS for layout */
    AppFooter > #footer-bindings {
        color: $text-muted;
    }
    AppFooter > #footer-info {
        color: $text-muted;
    }
    """

    def __init__(self, bindings: List[Tuple[str, str, str]], **kwargs):
        super().__init__(**kwargs)
        # Store only the relevant parts for display (key, description)
        self._bindings_data = [(key, desc) for key, _, desc in bindings]

    def compose(self) -> ComposeResult:
        yield Static(id="footer-bindings")
        yield Static(id="footer-info")

    def on_mount(self) -> None:
        """Called when the footer is mounted."""
        self._update_bindings()
        self._update_info() # Initial update
        self.set_interval(1, self._update_info) # Update info every second

    def _update_bindings(self) -> None:
        """Formats and displays the key bindings."""
        b = self.query_one("#footer-bindings", Static)
        # Format bindings similar to Textual's default Footer
        bindings_text = " | ".join(f"[dim]{key}[/]:{desc}" for key, desc in self._bindings_data) # Removed space for brevity
        b.update(bindings_text)

    def _update_info(self) -> None:
        """Updates the time and author information."""
        info_widget = self.query_one("#footer-info", Static)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        author = "Author: Liang,Yi" # Shortened for space

        # Let App CSS handle alignment
        info_text = f"{now_str} | {author}"
        info_widget.update(info_text) 