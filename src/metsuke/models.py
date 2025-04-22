# -*- coding: utf-8 -*-
"""Pydantic models and TypedDicts for Metsuke project structure."""
# Note: Pydantic models are the primary source of truth for validation.
# TypedDicts are included for potential use by the TUI if direct dict access is preferred,
# but using Pydantic model instances (.project.name etc.) is recommended.

from typing import List, Optional, TypedDict, Literal
from datetime import datetime
from pydantic import BaseModel, Field


# --- Pydantic Models (Used by core.py for validation) ---

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: Literal['pending', 'in_progress', 'Done', 'blocked']
    priority: Literal['low', 'medium', 'high']
    dependencies: List[int] = Field(default_factory=list)
    completion_date: Optional[datetime] = None


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