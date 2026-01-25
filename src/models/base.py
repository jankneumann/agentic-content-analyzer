"""SQLAlchemy declarative base.

This module provides the shared Base class for all SQLAlchemy models.
All database models should inherit from this Base.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
