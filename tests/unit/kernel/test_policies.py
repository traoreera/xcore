"""
Tests for Policy system.
"""

import pytest

from xcore.kernel.permissions.policies import Policy, PolicyEffect, PolicySet


class TestPolicyEffect:
    """Test PolicyEffect enum."""

    def test_allow_value(self):
        """Test ALLOW value."""
        assert PolicyEffect.ALLOW == "allow"
        assert PolicyEffect.ALLOW.value == "allow"

    def test_deny_value(self):
        """Test DENY value."""
        assert PolicyEffect.DENY == "deny"
        assert PolicyEffect.DENY.value == "deny"


class TestPolicy:
    """Test Policy dataclass."""

    def test_creation(self):
        """Test basic policy creation."""
        policy = Policy(
            resource="db.*", actions=["read", "write"], effect=PolicyEffect.ALLOW
        )
        assert policy.resource == "db.*"
        assert policy.actions == ["read", "write"]
        assert policy.effect == PolicyEffect.ALLOW

    def test_default_effect(self):
        """Test default effect is ALLOW."""
        policy = Policy(resource="*", actions=["*"])
        assert policy.effect == PolicyEffect.ALLOW

    def test_matches_exact_resource(self):
        """Test exact resource matching."""
        policy = Policy(resource="db.users", actions=["read"])
        assert policy.matches("db.users", "read") is True
        assert policy.matches("db.users", "write") is False
        assert policy.matches("db.posts", "read") is False

    def test_matches_wildcard_resource(self):
        """Test wildcard resource matching."""
        policy = Policy(resource="db.*", actions=["read"])
        assert policy.matches("db.users", "read") is True
        assert policy.matches("db.posts", "read") is True
        assert policy.matches("cache.items", "read") is False

    def test_matches_wildcard_action(self):
        """Test wildcard action matching."""
        policy = Policy(resource="db.*", actions=["*"])
        assert policy.matches("db.users", "read") is True
        assert policy.matches("db.users", "write") is True
        assert policy.matches("db.users", "delete") is True

    def test_matches_combined_wildcards(self):
        """Test combined wildcards."""
        policy = Policy(resource="*", actions=["*"])
        assert policy.matches("anything", "anything") is True

    def test_from_dict_basic(self):
        """Test from_dict with basic data."""
        data = {"resource": "db.*",
                "actions": ["read", "write"], "effect": "allow"}
        policy = Policy.from_dict(data)
        assert policy.resource == "db.*"
        assert policy.actions == ["read", "write"]
        assert policy.effect == PolicyEffect.ALLOW

    def test_from_dict_string_actions(self):
        """Test from_dict with string actions."""
        data = {"resource": "db.*", "actions": "read", "effect": "deny"}
        policy = Policy.from_dict(data)
        assert policy.actions == ["read"]
        assert policy.effect == PolicyEffect.DENY

    def test_from_dict_invalid_effect(self):
        """Test from_dict with invalid effect."""
        data = {"resource": "db.*", "actions": ["read"], "effect": "invalid"}
        with pytest.raises(ValueError) as exc_info:
            Policy.from_dict(data)
        assert "effect invalide" in str(exc_info.value)

    def test_from_dict_default_effect(self):
        """Test from_dict with missing effect."""
        data = {"resource": "db.*", "actions": ["read"]}
        policy = Policy.from_dict(data)
        assert policy.effect == PolicyEffect.ALLOW


class TestPolicySet:
    """Test PolicySet class."""

    @pytest.fixture
    def sample_policies(self):
        """Create sample policies."""
        return [
            Policy(resource="db.*",
                   actions=["read"], effect=PolicyEffect.ALLOW),
            Policy(resource="db.*",
                   actions=["write"], effect=PolicyEffect.DENY),
            Policy(resource="cache.*",
                   actions=["*"], effect=PolicyEffect.ALLOW),
        ]

    def test_creation(self, sample_policies):
        """Test basic PolicySet creation."""
        ps = PolicySet(plugin_name="test_plugin", policies=sample_policies)
        assert ps.plugin_name == "test_plugin"
        assert len(ps.policies) == 3

    def test_evaluate_allow(self, sample_policies):
        """Test evaluate returns ALLOW."""
        ps = PolicySet(plugin_name="test", policies=sample_policies)
        assert ps.evaluate("db.users", "read") == PolicyEffect.ALLOW
        assert ps.evaluate("cache.items", "write") == PolicyEffect.ALLOW

    def test_evaluate_deny(self, sample_policies):
        """Test evaluate returns DENY."""
        ps = PolicySet(plugin_name="test", policies=sample_policies)
        assert ps.evaluate("db.users", "write") == PolicyEffect.DENY

    def test_evaluate_no_match(self, sample_policies):
        """Test evaluate returns DENY when no policy matches."""
        ps = PolicySet(plugin_name="test", policies=sample_policies)
        assert ps.evaluate("unknown.resource", "action") == PolicyEffect.DENY

    def test_evaluate_first_match_wins(self):
        """Test first matching policy wins."""
        policies = [
            Policy(resource="*", actions=["*"], effect=PolicyEffect.DENY),
            Policy(resource="db.*", actions=["*"], effect=PolicyEffect.ALLOW),
        ]
        ps = PolicySet(plugin_name="test", policies=policies)
        # First policy denies everything
        assert ps.evaluate("db.users", "read") == PolicyEffect.DENY

    def test_allows(self, sample_policies):
        """Test allows convenience method."""
        ps = PolicySet(plugin_name="test", policies=sample_policies)
        assert ps.allows("db.users", "read") is True
        assert ps.allows("db.users", "write") is False

    def test_from_list(self):
        """Test from_list factory method."""
        raw_policies = [
            {"resource": "db.*", "actions": ["read"], "effect": "allow"},
            {"resource": "cache.*", "actions": ["*"], "effect": "allow"},
        ]
        ps = PolicySet.from_list("test_plugin", raw_policies)
        assert ps.plugin_name == "test_plugin"
        assert len(ps.policies) == 2

    def test_allow_all(self):
        """Test allow_all factory method."""
        ps = PolicySet.allow_all("test_plugin")
        assert ps.plugin_name == "test_plugin"
        assert len(ps.policies) == 1
        assert ps.policies[0].resource == "*"
        assert ps.policies[0].actions == ["*"]
        assert ps.policies[0].effect == PolicyEffect.ALLOW
        assert ps.allows("anything", "anything") is True

    def test_deny_all(self):
        """Test deny_all factory method."""
        ps = PolicySet.deny_all("test_plugin")
        assert ps.plugin_name == "test_plugin"
        assert len(ps.policies) == 0
        assert ps.evaluate("anything", "anything") == PolicyEffect.DENY
        assert ps.allows("anything", "anything") is False

    def test_to_list(self):
        """Test to_list serialization."""
        policies = [
            Policy(resource="db.*",
                   actions=["read"], effect=PolicyEffect.ALLOW),
        ]
        ps = PolicySet(plugin_name="test", policies=policies)
        result = ps.to_list()
        assert len(result) == 1
        assert result[0]["resource"] == "db.*"
        assert result[0]["actions"] == ["read"]
        assert result[0]["effect"] == "allow"

    def test_repr(self):
        """Test __repr__ method."""
        ps = PolicySet(
            plugin_name="test", policies=[Policy(resource="*", actions=["*"])]
        )
        repr_str = repr(ps)
        assert "test" in repr_str
        assert "rules=1" in repr_str


class TestPolicySetEdgeCases:
    """Test edge cases for PolicySet."""

    def test_empty_policy_set(self):
        """Test behavior with empty policy set."""
        ps = PolicySet(plugin_name="test", policies=[])
        assert ps.evaluate("any", "action") == PolicyEffect.DENY

    def test_order_matters(self):
        """Test that policy order affects evaluation."""
        # More specific policy first
        policies_ordered = [
            Policy(resource="db.users", actions=[
                   "read"], effect=PolicyEffect.ALLOW),
            Policy(resource="db.*", actions=["*"], effect=PolicyEffect.DENY),
        ]
        ps = PolicySet(plugin_name="test", policies=policies_ordered)
        assert ps.allows("db.users", "read") is True
        assert ps.allows("db.posts", "read") is False  # Falls through to deny

    def test_partial_wildcard_match(self):
        """Test partial wildcard in resource."""
        policies = [
            Policy(resource="db.*.read",
                   actions=["*"], effect=PolicyEffect.ALLOW),
        ]
        ps = PolicySet(plugin_name="test", policies=policies)
        assert ps.allows("db.users.read", "anything") is True
        assert ps.allows("db.users.write", "anything") is False

    def test_complex_wildcard_pattern(self):
        """Test complex wildcard patterns."""
        policies = [
            Policy(resource="db.user*.*",
                   actions=["read"], effect=PolicyEffect.ALLOW),
        ]
        ps = PolicySet(plugin_name="test", policies=policies)
        assert ps.allows("db.user1.profile", "read") is True
        assert ps.allows("db.user2.settings", "read") is True
