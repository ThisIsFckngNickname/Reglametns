"""
Document status enum.
"""
from enum import Enum


class DocumentStatus(str, Enum):
    """Document lifecycle statuses."""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

    @classmethod
    def _missing_(cls, value):
        """Allow case-insensitive lookup for backward compatibility."""
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None
