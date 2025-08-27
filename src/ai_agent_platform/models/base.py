"""
Base models with security and audit features.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_mixin

from ..database.connection import Base


@declarative_mixin
class TimestampMixin:
    """Mixin for automatic timestamp tracking."""

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


@declarative_mixin
class UUIDMixin:
    """Mixin for UUID primary keys."""

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


@declarative_mixin
class AuditMixin:
    """Mixin for audit trail tracking."""

    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)

    # Soft delete support
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(255), nullable=True)

    # Version tracking for optimistic locking
    version = Column(String(64), nullable=False, default="1")

    def mark_deleted(self, deleted_by: Optional[str] = None):
        """Mark record as deleted (soft delete)."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by

    def update_version(self):
        """Update version hash for optimistic locking."""
        content = f"{self.id}{datetime.now(timezone.utc).isoformat()}"
        self.version = hashlib.sha256(content.encode()).hexdigest()[:16]


@declarative_mixin
class SecureDataMixin:
    """Mixin for secure data handling."""

    # Encrypted JSON field for sensitive data
    encrypted_data = Column(Text, nullable=True)

    # Data classification
    data_classification = Column(
        String(20),
        default="internal",  # public, internal, confidential, restricted
        nullable=False,
    )

    @hybrid_property
    def is_sensitive(self) -> bool:
        """Check if data contains sensitive information."""
        return self.data_classification in ["confidential", "restricted"]

    def set_encrypted_data(
        self, data: Dict[str, Any], encryption_key: Optional[str] = None
    ):
        """Store encrypted data (placeholder - implement actual encryption)."""
        # TODO: Implement proper encryption with key management
        # For now, store as JSON with warning
        if self.is_sensitive and not encryption_key:
            raise ValueError("Encryption key required for sensitive data")

        self.encrypted_data = json.dumps(data, default=str)

    def get_decrypted_data(
        self, encryption_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve and decrypt data."""
        if not self.encrypted_data:
            return None

        # TODO: Implement proper decryption
        if self.is_sensitive and not encryption_key:
            raise ValueError("Encryption key required for sensitive data")

        return json.loads(self.encrypted_data)


class BaseModel(Base, UUIDMixin, TimestampMixin, AuditMixin):
    """Base model with all security features."""

    __abstract__ = True

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert model to dictionary with security filtering."""
        result = {}

        for column in self.__table__.columns:
            value = getattr(self, column.name)

            # Convert UUID to string
            if isinstance(value, uuid.UUID):
                value = str(value)

            # Convert datetime to ISO format
            elif isinstance(value, datetime):
                value = value.isoformat()

            # Filter sensitive data
            if not include_sensitive and column.name in [
                "encrypted_data",
                "deleted_by",
                "created_by",
                "updated_by",
            ]:
                continue

            result[column.name] = value

        return result

    def __repr__(self) -> str:
        """Safe string representation without sensitive data."""
        return f"<{self.__class__.__name__}(id={self.id})>"
