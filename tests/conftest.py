"""conftest.py: install a CDK stub so connector.py can be imported without the CDK package."""

import os
import sys
import types
from unittest.mock import MagicMock

# Add repo root to sys.path so tests can import connector directly.
_repo_root = os.path.dirname(os.path.dirname(__file__))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


def _install_cdk_stub() -> None:
    if "cdk" in sys.modules:
        return

    cdk = types.ModuleType("cdk")
    cdk_sql = types.ModuleType("cdk.sql")
    cdk_sql_dialects = types.ModuleType("cdk.sql.dialects")
    cdk_sql_generic = types.ModuleType("cdk.sql.generic")

    class SqlDialect:
        name = ""
        system_schemas: tuple = ()
        supports_upsert_adbc = False

        def schema_is_implicit_default(self, schema_name: str) -> bool:
            return False

        def adbc_ingest_kwargs(self, address: object) -> dict:
            return {}

        def adbc_stage_table_sql(self, stage_qualified: str, target_qualified: str) -> str:
            return f"CREATE TABLE {stage_qualified} AS SELECT * FROM {target_qualified} WHERE 1=0"

    class GenericSQLConnector:
        dialect_class = None

    cdk_sql_dialects.SqlDialect = SqlDialect
    cdk_sql_dialects.TableAddress = MagicMock
    cdk_sql_generic.GenericSQLConnector = GenericSQLConnector

    cdk.sql = cdk_sql
    cdk_sql.dialects = cdk_sql_dialects
    cdk_sql.generic = cdk_sql_generic

    sys.modules["cdk"] = cdk
    sys.modules["cdk.sql"] = cdk_sql
    sys.modules["cdk.sql.dialects"] = cdk_sql_dialects
    sys.modules["cdk.sql.generic"] = cdk_sql_generic


_install_cdk_stub()
