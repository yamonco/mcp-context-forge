# -*- coding: utf-8 -*-
"""Location: ./tests/unit/mcpgateway/db/test_gateway_lifecycle_repair_migration.py
Copyright contributors to the MCP-CONTEXT-FORGE project
SPDX-License-Identifier: Apache-2.0

Tests for the gateway lifecycle repair migration.
"""

# Standard
import importlib
import inspect as pyinspect

# Third-Party
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import sqlalchemy as sa


MODULE_NAME = "mcpgateway.alembic.versions.b7a3c9d1e5f2_repair_gateway_lifecycle_fields"
CANONICAL_MODULE_NAME = "mcpgateway.alembic.versions.6c0e5f8a9b1d_add_gateway_lifecycle_fields"
REVISION = "b7a3c9d1e5f2"  # pragma: allowlist secret
DOWN_REVISION = "e198602c3c1e"  # pragma: allowlist secret
NEXT_REVISION = "279184dfd71d"  # pragma: allowlist secret
HEAD_REVISION = "b6c7d8e9f0a1"  # pragma: allowlist secret


def _migration_context(connection: sa.Connection) -> MigrationContext:
    """Create a migration context for a connection."""
    return MigrationContext.configure(connection, opts={"as_sql": False})


def _create_gateway_table(connection: sa.Connection) -> None:
    """Create the table as it appeared after the skipped migration."""
    connection.execute(
        sa.text(
            """
            CREATE TABLE gateways (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(255) NOT NULL,
                url VARCHAR(767) NOT NULL
            )
            """
        )
    )


def test_repair_migration_metadata_and_contract_owner() -> None:
    """Repair is a new head that delegates to the published schema owner."""
    module = importlib.import_module(MODULE_NAME)
    canonical = importlib.import_module(CANONICAL_MODULE_NAME)

    assert module.revision == REVISION
    assert module.down_revision == DOWN_REVISION
    assert module._lifecycle_migration() is canonical
    assert len(pyinspect.signature(module.upgrade).parameters) == 0
    assert len(pyinspect.signature(module.downgrade).parameters) == 0


def test_repair_upgrade_is_idempotent_after_gateway_table_creation() -> None:
    """A table created after the old migration receives the contract once."""
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            _create_gateway_table(connection)
            context = _migration_context(connection)
            with Operations.context(context):
                module = importlib.import_module(MODULE_NAME)
                module.upgrade()
                module.upgrade()

            canonical = importlib.import_module(CANONICAL_MODULE_NAME)
            columns = {column["name"] for column in sa.inspect(connection).get_columns(canonical.GATEWAY_TABLE)}
            indexes = {index["name"] for index in sa.inspect(connection).get_indexes(canonical.GATEWAY_TABLE)}

            assert set(canonical.LIFECYCLE_COLUMNS) <= columns
            assert {canonical.LIFECYCLE_INDEX, canonical.CLAIM_INDEX} <= indexes
    finally:
        engine.dispose()


def test_repair_revision_has_an_upgrade_path_to_the_single_head() -> None:
    """A database stamped at the deployed repair revision reaches current head."""
    config = Config("mcpgateway/alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == [HEAD_REVISION]
    steps = [str(step) for step in script._upgrade_revs("heads", REVISION)]
    assert any(NEXT_REVISION in step for step in steps)
    assert any(HEAD_REVISION in step for step in steps)
