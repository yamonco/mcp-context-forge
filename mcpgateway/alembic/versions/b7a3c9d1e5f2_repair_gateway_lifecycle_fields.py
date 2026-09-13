# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/alembic/versions/b7a3c9d1e5f2_repair_gateway_lifecycle_fields.py
Copyright contributors to the MCP-CONTEXT-FORGE project
SPDX-License-Identifier: Apache-2.0

Repair gateway lifecycle fields skipped before the table existed.

Revision ID: b7a3c9d1e5f2
Revises: e198602c3c1e
Create Date: 2026-09-03
"""

# Standard
import importlib
from types import ModuleType
from typing import Sequence, Union


revision: str = "b7a3c9d1e5f2"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = "e198602c3c1e"  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LIFECYCLE_MIGRATION = "mcpgateway.alembic.versions.6c0e5f8a9b1d_add_gateway_lifecycle_fields"


def _lifecycle_migration() -> ModuleType:
    """Return the published migration that owns the lifecycle schema contract."""
    return importlib.import_module(_LIFECYCLE_MIGRATION)


def upgrade() -> None:
    """Apply the canonical lifecycle contract after gateways exists."""
    _lifecycle_migration().upgrade()


def downgrade() -> None:
    """Leave fields owned by the earlier lifecycle migration intact."""
