# -*- coding: utf-8 -*-
# Standard Python Libraries
"""Metsuke package.

Your one-stop shop for managing AI-assisted development projects.
"""

__version__ = "0.1.0"

# Expose core functionalities and models
from .core import load_plan
from .models import Project, ProjectMeta, Task
from .exceptions import MetsukeError, PlanLoadingError, PlanValidationError

__all__ = [
    "load_plan",
    "Project",
    "ProjectMeta",
    "Task",
    "MetsukeError",
    "PlanLoadingError",
    "PlanValidationError",
    "__version__",
] 