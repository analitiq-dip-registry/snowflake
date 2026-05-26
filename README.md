# Snowflake

Snowflake is a fully managed cloud data warehouse for analytics workloads. This connector provides authenticated read access to Snowflake schemas and tables via the official `snowflake-sqlalchemy` driver over always-on HTTPS/TLS.

## What is this?

This is a **connector** — a configuration that defines how to authenticate with Snowflake and what data is available for reading and writing. It does not move data by itself. Instead, it is used by the [Analitiq](https://analitiq-app.com) data integration platform or the open-source `analitiq-dip-registry` engine to set up data pipelines.

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

- A Snowflake account (any edition).
- A Snowflake user with a password and at least one role granted.
- A virtual warehouse the user is authorised to use (required for any query that consumes compute).
- Optional: a default database and schema; if omitted the session falls back to the user's defaults (schema defaults to `PUBLIC` when a database is selected).

## Authentication

This connector authenticates against Snowflake with a **username and password** over HTTPS. Snowflake's transport is always TLS-encrypted on port 443 — there is no plaintext mode and no user-controllable `sslmode` setting, so the connector does not expose one.

### How to get your credentials

1. Sign in to your Snowflake account (`https://<account>.snowflakecomputing.com`).
2. Note your **account identifier** — the preferred form is `<orgname>-<account_name>` (visible under *Admin → Accounts*). Legacy locator form (e.g. `xy12345.us-east-2.aws`) is also accepted. This is the identifier only, **not** a full hostname.
3. Confirm the **username** and **password** you intend to use. For production setups, create a dedicated service user rather than reusing a human account.
4. Identify the **warehouse**, **role**, and (optionally) the **database** and **schema** the connection should default to.

## Available Endpoints

This is a database connector. There are no statically declared endpoints — tables and views are discovered at connection time from `SNOWFLAKE.ACCOUNT_USAGE` (the `INFORMATION_SCHEMA` is excluded from listings). The supplied role must be able to read `ACCOUNT_USAGE` for discovery to succeed.

## Limitations

- **Compute cost** — every query (including the discovery queries and any connection test) runs on the chosen warehouse and consumes credits. If the warehouse is suspended it will auto-resume on first use.
- **Account identifier vs hostname** — the `account` field expects the identifier (`myorg-myaccount` or legacy `xy12345.us-east-2.aws`) and not the full `*.snowflakecomputing.com` URL. Supplying a full hostname will fail.
- **TLS is implicit** — Snowflake is always TLS over HTTPS; there is no `sslmode` knob and no `ssl_ca_certificate` input. CA verification is handled by the driver against system trust roots.
- **Warehouse selection** — a warehouse must be set (via this connector's `warehouse` input, on the role's user default, or by session policy) before any compute-consuming query can run.
- **Discovery role privileges** — the discovery strategy reads `SNOWFLAKE.ACCOUNT_USAGE`. Roles without this access will see an empty resource list.

## For AI agents

This connector includes `CLAUDE.md` and `AGENTS.md` files — machine-readable references used by AI agents and agentic frameworks. They document authentication types, available endpoints, post-auth steps, and any caveats for programmatic use. Both files are kept identical — `CLAUDE.md` is for Claude Code, `AGENTS.md` is for other agent frameworks.

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

- [Snowflake SQLAlchemy documentation](https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy)
- [Snowflake account identifier docs](https://docs.snowflake.com/en/user-guide/admin-account-identifier)
- [Analitiq Cloud](https://analitiq-app.com)
- [Analitiq Engine (open source)](https://github.com/analitiq-ai/analitiq-engine)
- [Analitiq DIP Registry (open source)](https://github.com/analitiq-dip-registry)
