# Snowflake

[![Status: unverified](https://img.shields.io/badge/status-unverified-orange)](https://github.com/analitiq-dip-registry)
[![Latest release](https://img.shields.io/github/v/release/analitiq-dip-registry/snowflake)](https://github.com/analitiq-dip-registry/snowflake/releases)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Connect to a [Snowflake](https://www.snowflake.com) cloud data warehouse and read data from any database, schema, and table your role can access. Uses the native ADBC Snowflake driver with standard username and password authentication over TLS.

## What is this?

This is a **connector** — a configuration that defines how to authenticate with Snowflake and how its databases, schemas, and tables are discovered for reading and writing. It does not move data by itself. Instead, it is used by the [Analitiq](https://analitiq-app.com) data integration platform or the open-source `analitiq-dip-registry` engine to set up data pipelines.

## How to use this connector

There are two ways to use this connector:

### Option 1 — Analitiq Cloud (no setup required)

All connectors from this registry are automatically available on [analitiq-app.com](https://analitiq-app.com). Simply log in, select the connector, and follow the on-screen instructions to connect your account.

### Option 2 — Open Source (self-hosted)

All connectors are open source and free to use. To get started:

1. Clone the [analitiq-dip-registry](https://github.com/analitiq-dip-registry) repository
2. Install the Claude plugin `analitiq-plugin-dataflow`
3. Launch Claude in the root directory of `analitiq-dip-registry`
4. Tell it: *"I need to move data from X to Y"*

The `analitiq-plugin-dataflow` plugin will automatically fetch the required connectors from the [Analitiq DIP Registry](https://github.com/analitiq-dip-registry) and set up the data flow pipeline for you.

## Prerequisites

Before you can connect, you need:

- A Snowflake account and its **account identifier** (e.g. `orgname-account_name`). This is the part of your Snowflake URL before `.snowflakecomputing.com`.
- A Snowflake **user** with a password and access to at least one warehouse, database, and schema.
- A **virtual warehouse** that the user can use to run queries (queries require an active warehouse).
- A **role** granting the privileges you need (optional — defaults to the user's default role).

## Authentication

This connector uses standard Snowflake **username and password** authentication. All communication runs over TLS — Snowflake is HTTPS-only, so there is no plaintext option and no TLS mode to configure.

The connection is established by the engine's native ADBC Snowflake driver. You provide the account identifier, username, and password; the warehouse, database, schema, and role are optional session defaults.

> **Note on other auth methods.** Snowflake also supports key-pair (JWT), OAuth, MFA, external-browser SSO, Okta, programmatic access tokens, and Workload Identity Federation. This connector targets the username + password model only. If you need one of the alternatives, open an issue or extend the connector with the builder plugin.

### Connection fields

| Field | Required | Description |
|-------|----------|-------------|
| `account` | yes | Snowflake account identifier (e.g. `orgname-account_name`), without the `.snowflakecomputing.com` suffix. |
| `username` | yes | Snowflake login username. |
| `password` | yes | Password for the user (stored as a secret). |
| `warehouse` | no | Default virtual warehouse used to run queries (e.g. `COMPUTE_WH`). |
| `database` | no | Default database for the session. |
| `schema` | no | Default schema within the database (defaults to `PUBLIC`). |
| `role` | no | Role used for authorization (defaults to the user's default role). |
| `host` | no | Explicit connection host override (normally derived from `account`). |
| `port` | no | Connection port (defaults to `443`). |

### How to get your credentials

1. Log in to your Snowflake account in the Snowsight web UI.
2. Find your **account identifier** — in Snowsight, open the account selector (bottom-left), and copy the account identifier in `orgname-account_name` form.
3. Use an existing user, or ask an admin to create one with `CREATE USER`. Make sure it has a password and is granted a role with the privileges you need (`GRANT ROLE ... TO USER ...`).
4. Confirm the user has access to a warehouse (`GRANT USAGE ON WAREHOUSE ... TO ROLE ...`) — queries cannot run without one.

## Available data

Snowflake is a database connector. Rather than a fixed set of endpoints, it discovers your databases, schemas, and tables at connection time and exposes them as resources you can read from or write to. Which objects are visible depends on the privileges of the role you connect with.

## Type mapping

Snowflake's native SQL types are mapped to Analitiq's canonical (Arrow-based) types by `definition/type-map-read.json`; the write direction (Arrow → Snowflake DDL) is defined in `definition/type-map-write.json`. Highlights:

- `NUMBER` / `DECIMAL` / `INT` → `Decimal128` (Snowflake's `INT` is `NUMBER(38,0)`)
- `FLOAT` / `DOUBLE` → `Float64`
- `VARCHAR` / `CHAR` / `STRING` → `Utf8`
- `BINARY` → `Binary`
- `DATE` → `Date32`, `TIME` → `Time64`
- `TIMESTAMP_NTZ` → `Timestamp`, `TIMESTAMP_LTZ` / `TIMESTAMP_TZ` → `Timestamp(..., UTC)`
- `VARIANT` / `OBJECT` / `ARRAY` / `MAP` / `VECTOR` → `Json`
- `GEOGRAPHY` / `GEOMETRY` → `Utf8` (serialized as text)

## Limitations

- **Warehouse required** — queries consume credits and require an active virtual warehouse. If no warehouse is set (and the user has no default), queries will fail.
- **TLS only** — all traffic is over HTTPS; there is no plaintext connection mode.
- **Auth scope** — only username + password authentication is supported by this connector (see the note above).
- **Visibility is role-scoped** — you can only see and query objects your role has been granted access to.
- **Writes land in the session schema** — the Snowflake ADBC driver has no per-statement schema/catalog targeting, so bulk writes always go to the connection's `schema` (default `PUBLIC`). Set `schema` to the intended write target.

## For AI agents

This connector includes `CLAUDE.md` and `AGENTS.md` files — machine-readable references used by AI agents and agentic frameworks. They document authentication types, connection fields, and any caveats for programmatic use. Both files are kept identical — `CLAUDE.md` is for Claude Code, `AGENTS.md` is for other agent frameworks.

## Create a connector to any system

You can create a new connector to any API or database using Claude and the Analitiq connector builder plugin:

1. Install [Claude Code](https://claude.ai/code)
2. Install the connector builder plugin:
   ```
   claude plugin add analitiq-dip-registry/analitiq-plugin-connector-builder
   ```
3. Launch Claude and say: *"I want to create a connector for [system name]"*
4. The plugin will interview you about the system, research its API documentation, and generate the full connector with all required files

No coding required — the plugin handles authentication research, endpoint schema generation, and file creation automatically.

![Example of Claude building a connector](media/example_1.png)

## Contributing

All connectors in this registry are community-maintained and live at [github.com/analitiq-dip-registry](https://github.com/analitiq-dip-registry). To add new endpoints or improve an existing connector, install the [connector builder plugin](https://github.com/analitiq-dip-registry/analitiq-plugin-connector-builder) and follow its instructions.

## Links

- [Snowflake Documentation](https://docs.snowflake.com)
- [ADBC Snowflake Driver](https://arrow.apache.org/adbc/current/driver/snowflake.html)
- [Analitiq Cloud](https://analitiq-app.com)
- [Analitiq Engine (open source)](https://github.com/analitiq-ai/analitiq-engine)
- [Analitiq DIP Registry (open source)](https://github.com/analitiq-dip-registry)
