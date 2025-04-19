# -*- coding: utf-8 -*-
"""Custom exceptions for Metsuke."""

class MetsukeError(Exception):
    """Base class for Metsuke exceptions."""
    pass

class PlanLoadingError(MetsukeError):
    """Error during plan file loading or parsing."""
    pass

class PlanValidationError(MetsukeError):
    """Error during plan schema validation."""
    pass 