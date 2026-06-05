"""Tests for PermissionValidator."""

import pytest
from xcore.kernel.permissions.validator import PermissionValidator, PermissionValidationError


class TestPermissionValidator:
    def setup_method(self):
        self.v = PermissionValidator()

    def test_none_permissions_valid(self):
        self.v.validate("plugin", None)  # should not raise

    def test_empty_list_valid(self):
        self.v.validate("plugin", [])  # should not raise

    def test_not_a_list_raises(self):
        with pytest.raises(PermissionValidationError, match="liste"):
            self.v.validate("plugin", {"resource": "db"})

    def test_rule_not_dict_raises(self):
        with pytest.raises(PermissionValidationError, match="dict"):
            self.v.validate("plugin", ["not_a_dict"])

    def test_missing_resource_raises(self):
        with pytest.raises(PermissionValidationError, match="resource"):
            self.v.validate("plugin", [{"effect": "allow", "actions": ["read"]}])

    def test_invalid_effect_raises(self):
        with pytest.raises(PermissionValidationError, match="effect"):
            self.v.validate("plugin", [{"resource": "db", "effect": "maybe"}])

    def test_actions_not_list_raises(self):
        with pytest.raises(PermissionValidationError, match="actions"):
            self.v.validate("plugin", [{"resource": "db", "actions": "read"}])

    def test_actions_empty_raises(self):
        with pytest.raises(PermissionValidationError, match="actions"):
            self.v.validate("plugin", [{"resource": "db", "actions": []}])

    def test_valid_allow_rule(self):
        self.v.validate("plugin", [
            {"resource": "db", "effect": "allow", "actions": ["read", "write"]}
        ])

    def test_valid_deny_rule(self):
        self.v.validate("plugin", [
            {"resource": "db", "effect": "deny", "actions": ["*"]}
        ])

    def test_default_effect_allow(self):
        self.v.validate("plugin", [{"resource": "db", "actions": ["read"]}])

    def test_multiple_rules(self):
        self.v.validate("plugin", [
            {"resource": "db", "effect": "allow", "actions": ["read"]},
            {"resource": "cache", "effect": "deny", "actions": ["*"]},
        ])

    def test_wildcard_actions(self):
        self.v.validate("plugin", [{"resource": "db", "actions": ["*"]}])
