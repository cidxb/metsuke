# tests/test_core.py
import pytest
from pathlib import Path

# Adjust import based on how pytest discovers modules.
# Assuming pytest runs from the root, this should work.
from src.metsuke.core import load_plans
from src.metsuke.exceptions import PlanLoadingError, PlanValidationError

# Define the path to the plan file relative to the project root
PLAN_FILE_PATH = Path("PROJECT_PLAN.yaml")

def test_load_plans_parses_project_name():
    """
    Tests that load_plans correctly parses the project name from PROJECT_PLAN.yaml.
    """
    # Ensure the plan file exists before running the test
    if not PLAN_FILE_PATH.is_file():
        pytest.skip(f"{PLAN_FILE_PATH} not found, skipping test.")

    try:
        # Load the plan using the defined path
        loaded_plans = load_plans([PLAN_FILE_PATH])
        
        # Check that the file was loaded successfully
        assert PLAN_FILE_PATH in loaded_plans
        project = loaded_plans[PLAN_FILE_PATH]
        assert project is not None, "Project should not be None"
        
        # Assert that the project name is correct
        assert project.project.name == "Metsuke"
    except (PlanLoadingError, PlanValidationError) as e:
        pytest.fail(f"load_plans raised an unexpected validation/loading error: {e}")
    except Exception as e:
        pytest.fail(f"load_plans failed unexpectedly: {e}")

# TODO: Add more tests for core functionality (e.g., loading non-existent file, invalid YAML, etc.) 