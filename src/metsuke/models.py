# -*- coding: utf-8 -*-
"""Pydantic models and TypedDicts for Metsuke project structure."""
# Note: Pydantic models are the primary source of truth for validation.
# TypedDicts are included for potential use by the TUI if direct dict access is preferred,
# but using Pydantic model instances (.project.name etc.) is recommended.

from typing import List, Optional, TypedDict, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator


# --- Pydantic Models (Used by core.py for validation) ---

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: Literal['pending', 'in_progress', 'Done', 'blocked']
    priority: Literal['low', 'medium', 'high']
    dependencies: List[int] = Field(default_factory=list)
    # --- Fields for time tracking (example) ---
    time_spent_seconds: float = 0.0
    # Note: current_session_start_time is intentionally not included here 
    # as it's runtime state, not persisted.

    # Optional: Add validators if needed
    # @validator('status') # Remove incomplete validator
    # def check_status(cls, v):
    #     allowed_statuses = ['pending', 'in_progress', 'Done', 'blocked']
    #     if v not in allowed_statuses:
    #         raise ValueError(f'Status must be one of {allowed_statuses}')
    #     return v


class ProjectMeta(BaseModel):
    name: str
    version: str
    license: Optional[str] = None


class Project(BaseModel):
    project: ProjectMeta
    context: Optional[str] = None
    tasks: List[Task] = Field(default_factory=list)
    focus: bool = False


# --- TypedDict Definitions (Mirroring Pydantic for TUI type hints if needed) ---
# Note: These were extracted from Metsuke.py. Using the Pydantic models above
# is generally preferred after core.load_plan() is called.

class TuiTaskDict(TypedDict):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    dependencies: List[int]

class TuiProjectMetaDict(TypedDict):
    name: str
    version: str

class TuiPlanDataDict(TypedDict):
    project: TuiProjectMetaDict
    tasks: List[TuiTaskDict]
    context: Optional[str] 