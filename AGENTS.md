---
name: snowflake
description: >
  Snowflake cloud data warehouse — username/password auth via the
  snowflake-sqlalchemy driver over always-on HTTPS/TLS.
type: database
---

# Snowflake

Fully managed cloud data warehouse for analytics workloads. Supports structured (NUMBER, VARCHAR, DATE, TIMESTAMP variants) and semi-structured (VARIANT, OBJECT, ARRAY) data, with always-on TLS and HTTPS-only transport.

## Authentication

### Database Credentials (username/password)
- Driver: snowflake (via `snowflake-sqlalchemy`)
- Default port: 443 (HTTPS, hard-coded by the driver)
- Connection string format: `snowflake://${user}:${password}@${account}/${database}/${schema}?warehouse=${warehouse}&role=${role}`
- TLS: always-on; the driver does not expose an `sslmode` parameter and no `ssl_ca_certificate` input is declared
- SSH tunnel support: no

## Post-Auth Steps

Resource discovery runs `on_activation` using the builtin `snowflake_account_usage` strategy. It enumerates databases, schemas, tables, and columns by reading `SNOWFLAKE.ACCOUNT_USAGE`. The `INFORMATION_SCHEMA` is excluded from listings.

## Caveats

- The `account` field is the Snowflake **account identifier**, not a hostname. Preferred form is `<orgname>-<account_name>` (e.g. `myorg-myaccount`); legacy locator form (e.g. `xy12345.us-east-2.aws`) is also accepted. Supplying a full `*.snowflakecomputing.com` URL will fail.
- A `warehouse` must be set before any compute-consuming query can run (via this connector's input, the user's default warehouse, or session policy). Suspended warehouses auto-resume on first query, which still consumes credits.
- If `schema` is omitted Snowflake defaults the session schema to `PUBLIC` when the chosen database has one. The connector defaults `schema` to `PUBLIC` in the UI to make this explicit.
- `database`, `schema`, and `role` are optional in the connection contract; only `account`, `user`, `password`, and `warehouse` are required.
- Numeric Snowflake types `INT`, `INTEGER`, `BIGINT`, and `SMALLINT` are aliases of `NUMBER(38, 0)` internally — they map to `Decimal128(38, 0)`, not Arrow integer types. `FLOAT` and `DOUBLE` are both stored as IEEE 754 double-precision and map to `Float64`.
- Semi-structured types (`VARIANT`, `OBJECT`, `ARRAY`) and geospatial types (`GEOGRAPHY`, `GEOMETRY`) are serialised as `Utf8` (JSON / WKT) for portability.
- Discovery requires the connecting role to be able to read `SNOWFLAKE.ACCOUNT_USAGE`. Roles without this access will see an empty resource list.
- No API rate limits apply — this is a direct database connection over the SQLAlchemy driver.
