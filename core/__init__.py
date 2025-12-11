"""
Core module - Client, Database, and Middlewares.
"""

from .client import app
from .database import Database, db

__all__ = ["app", "Database", "db"]
