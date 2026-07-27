---
name: Snowflake
description: >
  Snowflake cloud data warehouse connector using the native ADBC Snowflake driver with username and password authentication over TLS.
type: database
---

# Snowflake

Snowflake is a cloud data warehouse. This connector reads from and writes to Snowflake using the engine's native ADBC Snowflake driver. Databases, schemas, and tables are discovered at connection time and scoped to the connecting role's privileges.

## Transport

- Type: `adbc`
- Driver: `snowflake`
- Connection state is passed entirely via `db_kwargs` (no DSN). Account/host/port, warehouse, database, schema, and role map to the `adbc.snowflake.sql.*` option namespace; `username`/`password` use the driver's top-level keys; `adbc.snowflake.sql.auth_type` is `auth_snowflake`; `adbc.snowflake.sql.uri.protocol` is pinned to `https`.

## SQL capabilities (write path)

`definition/connector.json` declares `sql_capabilities` — load-bearing data the engine reads at `configure_schema`; without it every write refuses rather than guessing a default.

| Key | Value | Why |
|-----|-------|-----|
| `catalog` | `full` | Snowflake's fully-qualified form is `database.schema.object`, and discovery produces catalog-bearing endpoints. Anything less refuses every write to a discovered table. |
| `session_targeting` | `session_default` | The ADBC driver has no per-statement ingest targeting, so the session's `database`/`schema` decide where landing happens. Declaring `per_statement` here would be refused by the ADBC backend as a declaration/dialect disagreement. |
| `merge_form` | `merge` | Snowflake implements SQL-standard `MERGE INTO` (no `ON CONFLICT`, no `ON DUPLICATE KEY`). |
| `bulk_load.adbc` | `adbc_ingest` | The driver owns the fast path (Arrow → Parquet → `PUT` → `COPY INTO`). Because the backend calls `cursor.adbc_ingest` directly on this branch, the dialect deliberately does **not** override `bulk_land`. |
| `stage.scope` | `temp` | A Snowflake `TEMPORARY` table is session-scoped, so the stage gets a bare, schema-less address that resolves through the same session namespace as the driver's untargeted ingest. This is what lets the *target* live in any database/schema while landing still works. A `real` stage would inherit the target's catalog and silently land in the wrong place. |
| `stage.schema` | `target` | No dedicated staging schema. |
| `stage.transactional_ddl` | `false` | Snowflake DDL implicitly commits the active transaction and cannot be rolled back. |
| `limits.max_identifier_len` | `255` | Snowflake's documented ceiling (characters; the engine enforces bytes, which is safe in this direction). Must stay in sync with `SnowflakeDialect.max_identifier_length`. |

`max_bind_params` is deliberately omitted — Snowflake documents no such limit, and the `adbc_ingest` landing path is bindless anyway.

## Dialect surface

`SnowflakeDialect` overrides exactly four things beyond `name`: `system_schemas`, `max_identifier_length`, `stage_table_sql`, `merge_statement_sql`, and `adbc_ingest_kwargs`. The CDK's conformance check audits the dialect's public surface, so nothing outside the sanctioned hook set may be added.

- `stage_table_sql(stage, target, *, temp)` renders `CREATE [TEMPORARY] TABLE <stage> LIKE <target>` — `LIKE` copies types, defaults, and constraints without data.
- `merge_statement_sql(...)` renders standard `MERGE INTO … USING … ON …`, degrading to an insert-only `WHEN NOT MATCHED` clause when every landed column is a conflict key.
- `adbc_ingest_kwargs` returns `{}` to suppress `adbc.ingest.target_db_schema` / `target_catalog`, which the Snowflake driver does not implement (forwarding either raises `NOT_IMPLEMENTED: [Snowflake] Unknown statement option …`).
- `empty_table_sql` stays on the ANSI base (`DELETE FROM`) — correct, and avoids `TRUNCATE`'s implicit commit.

## Authentication

### Database (username + password)
- Auth type: `db`
- Client app required: no
- Credentials: `username` + `password` (password stored in `secrets`).
- Transport security: TLS always on (Snowflake is HTTPS-only). No TLS mode is selectable and there is no plaintext option.

Other Snowflake auth methods (key-pair/JWT, OAuth, MFA, external-browser SSO, Okta, programmatic access token, Workload Identity Federation) are NOT covered by this connector.

## Connection fields

| Field | Required | Storage | Description |
|-------|----------|---------|-------------|
| `account` | yes | connection.parameters | Account identifier (`orgname-account_name`), no `.snowflakecomputing.com` suffix. |
| `username` | yes | connection.parameters | Snowflake login username. |
| `password` | yes | secrets | User password. |
| `warehouse` | no | connection.parameters | Default virtual warehouse for query execution. |
| `database` | no | connection.parameters | Default database. |
| `schema` | no | connection.parameters | Default schema (defaults to `PUBLIC`). |
| `role` | no | connection.parameters | Authorization role (defaults to user's default role). |
| `host` | no | connection.parameters | Explicit host override (normally derived from `account`). |
| `port` | no | connection.parameters | Connection port (defaults to `443`). |

## Resource discovery

- Strategy: `snowflake_account_usage` (builtin).
- Databases / schemas / tables are enumerated at connection time; visibility is role-scoped.
- Produces `connection.endpoints` and `connection.type_map`.

## Type mapping

Read direction (native → Arrow) is defined in `definition/type-map-read.json`; write direction (Arrow → native DDL) in `definition/type-map-write.json`. The read map covers the full Snowflake type vocabulary including declared aliases (`NUMERIC`/`DEC`/`INTEGER`/`BIGINT`/…, `TEXT`/`CHARACTER`/`NVARCHAR`/…, `FLOAT4`/`FLOAT8`/`DOUBLE PRECISION`/`REAL`, `DATETIME`, bare `TIMESTAMP`) so discovery output resolves whether Snowflake emits canonical or alias tokens. Notable mappings:

- `NUMBER` / `DECIMAL` / `NUMERIC` / `DEC` / `INT` (and integer aliases) → `Decimal128` (parameterized `NUMBER(p,s)` preserves precision/scale; `INT` and friends are `NUMBER(38,0)`).
- `FLOAT` / `FLOAT4` / `FLOAT8` / `DOUBLE` / `DOUBLE PRECISION` / `REAL` → `Float64`.
- `VARCHAR` / `CHAR` / `STRING` / `TEXT` / `CHARACTER` / `NCHAR` / `NVARCHAR` (and length-qualified forms) → `Utf8`.
- `BINARY` / `VARBINARY` → `Binary`.
- `DATE` → `Date32`; `TIME` → `Time64(NANOSECOND)`.
- `TIMESTAMP_NTZ` / `DATETIME` / bare `TIMESTAMP` → `Timestamp(NANOSECOND)`; `TIMESTAMP_LTZ` / `TIMESTAMP_TZ` → `Timestamp(NANOSECOND, UTC)`.
- `VARIANT` / `OBJECT` / `ARRAY` / `MAP` / `VECTOR(<type>, <dim>)` → `Json`, plus the structured spellings `ARRAY(<t>)` / `OBJECT(<k> <t>, …)` / `MAP(<k>, <v>)`.
- `GEOGRAPHY` / `GEOMETRY` → `Utf8` (serialized as text).
- `UUID` → `Utf8` (Snowflake renders the 36-character hyphenated form).

**Deliberately unmapped:** `DECFLOAT` and `FILE`. Neither has a documented ADBC Arrow representation — `DECFLOAT`'s exponent range does not fit `Decimal128` and `Float64` cannot hold its 38 significant digits; `FILE` is a staged-file reference, not a value. Both are left to raise a loud `UnmappedTypeError` naming the type rather than being guessed into a lossy canonical. Close them when the driver documents a mapping. `BLOB`, `CLOB`, and `ENUM` are documented by Snowflake as unsupported and are not mapped.

**Precision assumptions:** the flat `NANOSECOND` mapping for every `TIME(n)` / `TIMESTAMP_*(n)` is correct because the driver normalizes all precisions to `[ns]` — it is not the usual digit→unit ladder. This holds only while the driver options `max_timestamp_precision` (default `nanoseconds`) and `use_high_precision` (default `true`) are at their defaults; neither is pinned in `db_kwargs`, because the exact namespaced key spelling is not documented.

The write direction renders canonical Arrow types back to Snowflake DDL (`Decimal128(p,s)` → `NUMBER(p,s)`, integers → `NUMBER(38,0)`, floats → `FLOAT`, `Utf8` → `VARCHAR`, `Binary` → `BINARY`, `Boolean` → `BOOLEAN`, `Date32` → `DATE`, `Time*` → `TIME`, `Timestamp(_)` → `TIMESTAMP_NTZ`, any zoned `Timestamp` → `TIMESTAMP_LTZ`, `Json` / `Object` / `List` → `VARIANT`, `Null` → `VARCHAR`, `Duration(_)` → `NUMBER(38,0)`).

Two intentional write-map limits: `Decimal` rules stop at Snowflake's real ceiling (precision ≤ 38, scale ≤ 37), so `Decimal256(76,0)` and `Decimal128(38,38)` refuse at configuration time instead of silently losing precision; and `Duration` renders as an integer count whose *unit* is not preserved in the DDL.

## Caveats

- Queries require an active virtual warehouse; set `warehouse` (or ensure the user has a default) or queries fail.
- All traffic is over TLS/HTTPS; there is no plaintext mode.
- Object visibility is limited to what the connecting role can access.
- **Writes require a session `database` AND `schema`, and `CREATE STAGE` on that schema.** The Snowflake ADBC driver implements no per-statement ingest schema/catalog targeting (`adbc_ingest_kwargs` returns `{}`), so each batch lands in a session-scoped temporary stage table and the driver's ingest creates a temporary internal stage in the session schema before `COPY INTO`. The *target* table may live in any database/schema the role can write — only the staging is session-bound. (This supersedes the previous "writes land in the session schema" caveat, which was true of the earlier `real`-stage shape.)
- **Upsert batches must be key-unique.** `ERROR_ON_NONDETERMINISTIC_MERGE` defaults to `TRUE`, so two rows sharing a conflict key in one batch fail the `MERGE`. The dialect does not de-duplicate: with no ordering column in the contract, any automatic pick would drop a row arbitrarily, so the error is allowed to surface.
- **Residual risk to smoke-test on first deploy:** `stage.scope: temp` assumes the driver's ingest runs in the same session as the `CREATE TEMPORARY TABLE`. That follows from the documented mechanism (a temporary internal stage is session-scoped, so the `COPY` must share the `PUT`'s session), but it was not verified against the driver source. If a future driver version pooled stages across connections, the fallback is `stage.scope: real` with `catalog` downgraded to `read`.
