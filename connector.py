"""Snowflake connector — dialect + connector class for the Analitiq CDK.

Everything Snowflake-specific lives here, in the connector package: the
catalog-schema exclusion for account-usage discovery, the Snowflake
``CREATE TEMPORARY TABLE … LIKE …`` stage form, the ``MERGE INTO`` upsert
statement, and the suppression of the per-statement ingest targeting that
the Snowflake ADBC driver does not implement.

The connector runs on the ADBC Snowflake driver (transport_type ``adbc``),
which hands Arrow buffers to Snowflake's native ingestion path (Parquet ->
PUT to a temporary internal stage -> COPY INTO). There is no SQLAlchemy
transport, so the SQLAlchemy/TLS hooks stay on the neutral base. Snowflake
is HTTPS/TLS-only over port 443 with no selectable TLS mode and no
CA-bundle driver option, so there is no ``ssl_mode`` input, no ``tls``
block, and no ``build_tls_connect_arg`` hook — the transport pins
``adbc.snowflake.sql.uri.protocol`` to ``https`` instead.

"No SQLAlchemy transport" covers only the connect/write path: no SQLAlchemy
``Engine`` is ever constructed here. The engine's shared read path still
compiles paged ``SELECT``s through SQLAlchemy Core and resolves this dialect
via ``sqlalchemy.dialects.registry.load("snowflake")``, so
``snowflake-sqlalchemy`` is a required runtime dependency (see
``requirements.txt``). The registered SA dialect name equals ``name``, so
``sqlalchemy_registry_name`` stays on the base default.

The write direction is fully declarative: ``definition/type-map-write.json``
owns every column-type render, so this dialect ships no Python
type-rendering table and needs no ``render_column_type`` override. The
write-path *shape* facts (catalog addressing, session targeting, merge
form, bulk mechanism, stage scope, identifier cap) are declared data in
``definition/connector.json`` under ``sql_capabilities`` — never class
booleans.

Registered under connector_id ``snowflake`` via the package entry points
(``analitiq.source_connectors`` / ``analitiq.destination_connectors``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from cdk.sql.dialects import SqlDialect
from cdk.sql.generic import GenericSQLConnector

if TYPE_CHECKING:
    from cdk.sql.dialects import TableAddress


class SnowflakeDialect(SqlDialect):
    """Snowflake SQL strategy: double-quoted identifiers, account-usage
    discovery, the Snowflake ``CREATE TABLE … LIKE …`` stage form, the
    ``MERGE INTO`` upsert statement, and no per-statement ingest targeting
    (the Snowflake ADBC driver does not implement it)."""

    name = "snowflake"
    # INFORMATION_SCHEMA is the per-database catalog; the shared SNOWFLAKE
    # database (ACCOUNT_USAGE / READER_ACCOUNT_USAGE) is enumerated by the
    # snowflake_account_usage strategy itself, not surfaced as a user schema.
    system_schemas = ("INFORMATION_SCHEMA",)
    # Snowflake's documented identifier ceiling is 255 characters; the base
    # default 63 is Postgres/Redshift NAMEDATALEN - 1 and is simply the wrong
    # fact for this system. It must agree with the connector's declared
    # sql_capabilities.limits.max_identifier_len: write_plan.identifier_budget
    # prefers the declaration and this attribute is the dialect's own fallback
    # assumption, so a dialect asserting 63 under a declared 255 states two
    # contradictory facts about one system (and fails the tier-1
    # stage-name-budget conformance check, which reads this attribute
    # precisely because the declared-budget reading would be vacuous).
    # The engine treats the number as BYTES while Snowflake documents it in
    # characters — safe in this direction, since bytes <= characters always.
    max_identifier_length = 255

    # ---- stage-then-merge write path -----------------------------------------
    def stage_table_sql(
        self, stage: TableAddress, target: TableAddress, *, temp: bool
    ) -> str:
        # ``LIKE`` copies the target's full column definitions (types,
        # defaults, collations, constraints) without data, so the stage is
        # always shaped exactly like what the batch is about to merge into.
        #
        # ``temp`` comes from the declared ``sql_capabilities.stage.scope``.
        # This connector declares ``temp``: a Snowflake TEMPORARY table is
        # session-scoped, so the CDK gives the stage a bare (schema-less)
        # address and every step of the cycle — CREATE, the driver's bulk
        # ingest, the MERGE/INSERT, the DROP — resolves that one name through
        # the same session namespace. That is what lets a write target any
        # database/schema the role can reach even though ``adbc_ingest``
        # cannot be targeted per statement (see ``adbc_ingest_kwargs``).
        scope = "TEMPORARY " if temp else ""
        return (
            f"CREATE {scope}TABLE {self.quote_table(stage)} "
            f"LIKE {self.quote_table(target)}"
        )

    def merge_statement_sql(
        self,
        stage: TableAddress,
        target: TableAddress,
        conflict_keys: Sequence[str],
        columns: Sequence[str],
    ) -> str:
        # Snowflake's declared merge form is SQL-standard ``MERGE INTO``
        # (no ON CONFLICT, no ON DUPLICATE KEY). Columns the target has but
        # the batch did not land keep their stored value on matched rows and
        # take their DEFAULT on inserted ones, per the CDK write contract.
        keys = set(conflict_keys)
        updatable = [c for c in columns if c not in keys]
        on_clause = " AND ".join(
            f"t.{self.quote_ident(c)} = s.{self.quote_ident(c)}"
            for c in conflict_keys
        )
        clauses: list[str] = []
        if updatable:
            assignments = ", ".join(
                f"t.{self.quote_ident(c)} = s.{self.quote_ident(c)}"
                for c in updatable
            )
            clauses.append(f"WHEN MATCHED THEN UPDATE SET {assignments}")
        # When every landed column is a conflict key there is nothing to
        # update: a MERGE with only a NOT MATCHED clause is the sanctioned
        # insert-only degradation — matched rows stay untouched, never an
        # error.
        insert_cols = ", ".join(self.quote_ident(c) for c in columns)
        insert_vals = ", ".join(f"s.{self.quote_ident(c)}" for c in columns)
        clauses.append(
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) "
            f"VALUES ({insert_vals})"
        )
        # Composed exclusively of dialect-quoted identifiers; values never
        # enter this text (they were landed into the stage separately).
        return (
            f"MERGE INTO {self.quote_table(target)} t "  # nosec B608
            f"USING {self.quote_table(stage)} s "
            f"ON {on_clause} " + " ".join(clauses)
        )

    # ---- ADBC ingest targeting -----------------------------------------------
    def adbc_ingest_kwargs(self, address: TableAddress) -> dict[str, Any]:  # skipcq: PYL-R0201
        # Overrides the base ``SqlDialect`` hook, so it keeps that hook's
        # ``(self, address)`` instance signature even though this
        # implementation uses neither — the R0201 "no-self-use, make it a
        # @staticmethod" hint is a false positive (a staticmethod would break
        # the override contract and diverge from the sibling overrides).
        #
        # The Snowflake ADBC driver does not implement
        # ``adbc.ingest.target_db_schema`` or ``adbc.ingest.target_catalog``;
        # forwarding either (the base default derives ``db_schema_name`` /
        # ``catalog_name`` from the address) raises, e.g.,
        # ``NOT_IMPLEMENTED: [Snowflake] Unknown statement option
        # 'adbc.ingest.target_db_schema'``. Returning no targeting kwargs lets
        # bulk ingest follow the connection's session database + schema
        # (``adbc.snowflake.sql.db`` / ``.schema``).
        #
        # That is safe here because the connector declares
        # ``sql_capabilities.stage.scope: "temp"``: the stage the batch lands
        # in is a session-scoped temporary table with a bare, schema-less
        # address, so "wherever the session points" is exactly where the
        # CREATE put it and where the MERGE reads it from. The target itself
        # is always fully qualified in engine-rendered SQL, so it may live in
        # any database/schema the role can write.
        #
        # Contract: the session must have a current database AND schema (the
        # connection's ``database`` / ``schema`` parameters), and the role
        # needs CREATE STAGE on that schema — the driver's ingest creates a
        # temporary internal stage there before COPY INTO.
        return {}


class SnowflakeConnector(GenericSQLConnector):
    """Snowflake connector: the CDK SQL base wired to the Snowflake dialect."""

    dialect_class = SnowflakeDialect
