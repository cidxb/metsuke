# -*- coding: utf-8 -*-
"""Core logic for Metsuke: loading, parsing, validating plans."""

import yaml
from pathlib import Path
from typing import Dict, Any

from pydantic import ValidationError

from .models import Project
from .exceptions import PlanLoadingError, PlanValidationError


def load_plan(filepath: Path = Path("PROJECT_PLAN.yaml")) -> Project:
    """Loads, parses, and validates the project plan YAML file.

    Args:
        filepath: The path to the project plan YAML file.
                  Defaults to "PROJECT_PLAN.yaml" in the current directory.

    Returns:
        A validated Project object.

    Raises:
        PlanLoadingError: If the file cannot be found or parsed as YAML.
        PlanValidationError: If the file content does not match the Project schema.
    """
    if not filepath.is_file():
        raise PlanLoadingError(f"Plan file not found at: {filepath.resolve()}")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data: Dict[Any, Any] = yaml.safe_load(f)
            if data is None: # Handle empty file case
                raise PlanLoadingError(f"Plan file is empty: {filepath.resolve()}")
    except FileNotFoundError:
        # Should be caught by is_file() check, but included for robustness
        raise PlanLoadingError(f"Plan file not found at: {filepath.resolve()}")
    except yaml.YAMLError as e:
        raise PlanLoadingError(f"Error parsing YAML file: {filepath.resolve()}\n{e}")
    except Exception as e: # Catch other potential file reading errors
        raise PlanLoadingError(f"Error reading file: {filepath.resolve()}\n{e}")

    try:
        project_data = Project.model_validate(data)
        return project_data
    except ValidationError as e:
        raise PlanValidationError(f"Plan validation failed for {filepath.resolve()}:\n{e}") 