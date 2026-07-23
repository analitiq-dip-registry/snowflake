"""Tests for SnowflakeDialect."""

import unittest

from connector import SnowflakeDialect


class TestSchemaIsImplicitDefault(unittest.TestCase):
    def setUp(self) -> None:
        self.dialect = SnowflakeDialect()

    def test_public_upper_is_implicit(self) -> None:
        self.assertTrue(self.dialect.schema_is_implicit_default("PUBLIC"))

    def test_public_lower_is_implicit(self) -> None:
        # Snowflake folds unquoted identifiers to uppercase; accept any case.
        self.assertTrue(self.dialect.schema_is_implicit_default("public"))

    def test_public_mixed_case_is_implicit(self) -> None:
        self.assertTrue(self.dialect.schema_is_implicit_default("Public"))

    def test_other_schema_is_not_implicit(self) -> None:
        self.assertFalse(self.dialect.schema_is_implicit_default("SALES"))

    def test_empty_string_is_not_implicit(self) -> None:
        self.assertFalse(self.dialect.schema_is_implicit_default(""))

    def test_prefix_match_is_not_implicit(self) -> None:
        self.assertFalse(self.dialect.schema_is_implicit_default("PUBLIC_SCHEMA"))


if __name__ == "__main__":
    unittest.main()
