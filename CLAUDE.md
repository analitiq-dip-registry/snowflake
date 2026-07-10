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
- Connection state is passed entirely via `db_kwargs` (no DSN). Account/host/port, warehouse, database, schema, and role map to the `adbc.snowflake.sql.*` option namespace; `username`/`password` use the driver's top-level keys; `adbc.snowflake.sql.auth_type` is `auth_snowflake`.

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
- `VARIANT` / `OBJECT` / `ARRAY` / `MAP` / `VECTOR(<type>, <dim>)` → `Json`.
- `GEOGRAPHY` / `GEOMETRY` → `Utf8` (serialized as text).

The write direction renders canonical Arrow types back to Snowflake DDL (`Decimal128(p,s)` → `NUMBER(p,s)`, integers → `NUMBER(38,0)`, floats → `FLOAT`, `Utf8` → `VARCHAR`, `Binary` → `BINARY`, `Boolean` → `BOOLEAN`, `Date32` → `DATE`, `Time*` → `TIME`, `Timestamp(_)` → `TIMESTAMP_NTZ`, `Timestamp(_, UTC)` → `TIMESTAMP_LTZ`, `Json` → `VARIANT`).

## Caveats

- Queries require an active virtual warehouse; set `warehouse` (or ensure the user has a default) or queries fail.
- All traffic is over TLS/HTTPS; there is no plaintext mode.
- Object visibility is limited to what the connecting role can access.
