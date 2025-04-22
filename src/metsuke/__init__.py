# -*- coding: utf-8 -*-
# Standard Python Libraries
"""Metsuke package.

Your one-stop shop for managing AI-assisted development projects.
"""

__version__ = "0.1.1"

# Expose core functionalities and models
from .core import find_plan_files, load_plans, save_plan, manage_focus
from .models import Project, ProjectMeta, Task
from .exceptions import MetsukeError, PlanLoadingError, PlanValidationError

__all__ = [
    "find_plan_files",
    "load_plans",
    "save_plan",
    "manage_focus",
    "Project",
    "ProjectMeta",
    "Task",
    "MetsukeError",
    "PlanLoadingError",
    "PlanValidationError",
    "__version__",
] 