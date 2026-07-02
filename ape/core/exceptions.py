"""
Custom exceptions for APE.
"""
class APEError(Exception):
    """Base exception for all APE errors."""

class ConfigError(APEError):
    """Configuration error."""

class DataValidationError(APEError):
    """Input data validation error."""

class ImporterError(APEError):
    """Importer error."""

class DatabaseError(APEError):
    """Database error."""

class EngineError(APEError):
    """Engine error."""
