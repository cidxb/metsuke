# tests/test_core.py
import pytest
from pathlib import Path

# Adjust import based on how pytest discovers modules.
# Assuming pytest runs from the root, this should work.
from src.metsuke.core import load_plan
from src.metsuke.exceptions import PlanLoadingError, PlanValidationError

# Define the path to the plan file relative to the project root
PLAN_FILE_PATH = Path("PROJECT_PLAN.yaml")

def test_load_plan_parses_project_name():
    """
    Tests that load_plan correctly parses the project name from PROJECT_PLAN.yaml.
    """
    # Ensure the plan file exists before running the test
    if not PLAN_FILE_PATH.is_file():
        pytest.skip(f"{PLAN_FILE_PATH} not found, skipping test.")

    try:
        # Load the plan using the defined path
        project = load_plan(filepath=PLAN_FILE_PATH)
        # Assert that the project name is correct
        assert project.project.name == "Metsuke"
    except (PlanLoadingError, PlanValidationError) as e:
        pytest.fail(f"load_plan raised an unexpected validation/loading error: {e}")
    except Exception as e:
        pytest.fail(f"load_plan failed unexpectedly: {e}")

# TODO: Add more tests for core functionality (e.g., loading non-existent file, invalid YAML, etc.) 