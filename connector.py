"""Snowflake connector — dialect + connector class for the Analitiq CDK.

Everything Snowflake-specific lives here, in the connector package: the
catalog-schema exclusion for account-usage discovery, the Snowflake
``CREATE TABLE … LIKE …`` stage-table form used by the ADBC MERGE upsert,
and the suppression of the per-statement ingest targeting the Snowflake
ADBC driver does not implement.

The connector runs on the ADBC Snowflake driver (transport_type ``adbc``),
which hands Arrow buffers to Snowflake's native ingestion path (PUT to an
internal stage + COPY INTO) — there is no SQLAlchemy transport, so the
SQLAlchemy/TLS hooks stay on the neutral base. Snowflake is HTTPS/TLS-only
over port 443 with no selectable TLS mode, so there is no ``ssl_mode``
input and no ``build_tls_connect_arg`` hook.

"No SQLAlchemy transport" covers only the connect/write path: no SQLAlchemy
``Engine`` is ever constructed here. The engine's shared read path still
compiles paged ``SELECT``s through SQLAlchemy Core and resolves this dialect
via ``sqlalchemy.dialects.registry.load("snowflake")``, so
``snowflake-sqlalchemy`` is a required runtime dependency (see
``requirements.txt``).

The write direction is fully declarative: ``definition/type-map-write.json``
owns every column-type render, so this dialect ships no Python
type-rendering table and needs no ``render_column_type`` override.

Registered under connector_id ``snowflake`` via the package entry points
(``analitiq.source_connectors`` / ``analitiq.destination_connectors``).
"""

from __future__ import annotations

from typing import Any

from cdk.sql.dialects import SqlDialect, TableAddress
from cdk.sql.generic import GenericSQLConnector


class SnowflakeDialect(SqlDialect):
    """Snowflake SQL strategy: double-quoted identifiers, account-usage
    discovery, the Snowflake ``CREATE TABLE … LIKE …`` stage-table form for
    the ADBC MERGE upsert, and no per-statement ingest targeting (the
    Snowflake ADBC driver does not support it)."""

    name = "snowflake"
    # INFORMATION_SCHEMA is the per-database catalog; the shared SNOWFLAKE
    # database (ACCOUNT_USAGE / READER_ACCOUNT_USAGE) is enumerated by the
    # snowflake_account_usage strategy itself, not surfaced as a user schema.
    system_schemas = ("INFORMATION_SCHEMA",)
    supports_upsert_adbc = True

    # ---- ADBC-only write path ------------------------------------------------
    def adbc_ingest_kwargs(self, address: TableAddress) -> dict[str, Any]:
        # The Snowflake ADBC driver implements neither
        # ``adbc.ingest.target_db_schema`` nor ``adbc.ingest.target_catalog``;
        # forwarding either (the base default derives ``db_schema_name`` /
        # ``catalog_name`` from the address) raises
        # ``NOT_IMPLEMENTED: Unknown statement option``. Return no targeting
        # kwargs so bulk ingest follows the connection's session schema
        # (``adbc.snowflake.sql.schema``), where the stage and target tables
        # already live.
        return {}

    def adbc_stage_table_sql(
        self, stage_qualified: str, target_qualified: str
    ) -> str:
        # Snowflake copies a table's full column definitions (types,
        # defaults, collations) with ``LIKE``; the base ADBC MERGE upsert
        # stages rows into this clone before merging into the target.
        return f"CREATE TABLE {stage_qualified} LIKE {target_qualified}"


class SnowflakeConnector(GenericSQLConnector):
    """Snowflake connector: the CDK SQL base wired to the Snowflake dialect."""

    dialect_class = SnowflakeDialect
