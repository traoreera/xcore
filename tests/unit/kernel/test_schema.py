"""Tests for SchemaRegistry and BreakingChangeDetector."""

import json
import pytest
from pathlib import Path

from xcore.kernel.schema.registry import ActionSchema, SchemaRegistry
from xcore.kernel.schema.checker import BreakingChange, BreakingChangeDetector


# ── ActionSchema ──────────────────────────────────────────────────────────────


class TestActionSchema:
    def test_key(self):
        s = ActionSchema(plugin="auth", action="login", version="1.0.0", input={}, output={})
        assert s.key == "auth:login"

    def test_to_dict_round_trip(self):
        s = ActionSchema(
            plugin="auth",
            action="login",
            version="1.0.0",
            input={"email": "str"},
            output={"token": "str"},
            deprecated_fields={"old_field": "use new_field"},
            breaking_since="2.0.0",
            description="Login action",
        )
        d = s.to_dict()
        s2 = ActionSchema.from_dict(d)
        assert s2 == s

    def test_from_dict_minimal(self):
        d = {
            "plugin": "shop",
            "action": "buy",
            "version": "1.0",
            "input": {},
            "output": {},
            "deprecated_fields": {},
            "breaking_since": None,
            "description": "",
        }
        s = ActionSchema.from_dict(d)
        assert s.plugin == "shop"
        assert s.action == "buy"


# ── SchemaRegistry ────────────────────────────────────────────────────────────


class TestSchemaRegistry:
    def test_register_and_get(self):
        reg = SchemaRegistry()
        s = ActionSchema(plugin="p", action="a", version="1.0", input={}, output={})
        reg.register(s)
        assert reg.get("p", "a") is s

    def test_get_missing(self):
        reg = SchemaRegistry()
        assert reg.get("nope", "nope") is None

    def test_get_by_key(self):
        reg = SchemaRegistry()
        s = ActionSchema(plugin="p", action="a", version="1.0", input={}, output={})
        reg.register(s)
        assert reg.get_by_key("p:a") is s
        assert reg.get_by_key("missing") is None

    def test_all(self):
        reg = SchemaRegistry()
        s1 = ActionSchema(plugin="p", action="a", version="1.0", input={}, output={})
        s2 = ActionSchema(plugin="p", action="b", version="1.0", input={}, output={})
        reg.register(s1)
        reg.register(s2)
        assert sorted(reg.all(), key=lambda s: s.action) == sorted([s1, s2], key=lambda s: s.action)

    def test_for_plugin(self):
        reg = SchemaRegistry()
        s1 = ActionSchema(plugin="auth", action="login", version="1.0", input={}, output={})
        s2 = ActionSchema(plugin="shop", action="buy", version="1.0", input={}, output={})
        reg.register(s1)
        reg.register(s2)
        assert reg.for_plugin("auth") == [s1]
        assert reg.for_plugin("shop") == [s2]
        assert reg.for_plugin("nope") == []

    def test_save_and_load(self, tmp_path):
        reg = SchemaRegistry()
        s = ActionSchema(
            plugin="auth",
            action="login",
            version="2.0",
            input={"email": "str", "password": "str"},
            output={"token": "str"},
        )
        reg.register(s)

        path = tmp_path / "schemas.json"
        reg.save(path)
        assert path.exists()

        reg2 = SchemaRegistry.load(path)
        s2 = reg2.get("auth", "login")
        assert s2 is not None
        assert s2.version == "2.0"
        assert s2.input == {"email": "str", "password": "str"}

    def test_load_missing_file(self, tmp_path):
        reg = SchemaRegistry.load(tmp_path / "nonexistent.json")
        assert reg.all() == []

    def test_load_corrupted_entry(self, tmp_path):
        path = tmp_path / "schemas.json"
        path.write_text(json.dumps({"bad:key": {"not": "valid", "schema": True}}))
        reg = SchemaRegistry.load(path)
        assert reg.all() == []

    def test_summary(self):
        reg = SchemaRegistry()
        s1 = ActionSchema(plugin="auth", action="login", version="1.0", input={}, output={})
        s2 = ActionSchema(plugin="shop", action="buy", version="2.0", input={}, output={})
        reg.register(s1)
        reg.register(s2)
        summary = reg.summary()
        assert summary["total"] == 2
        assert "auth" in summary["plugins"]
        assert "shop" in summary["plugins"]
        assert len(summary["actions"]) == 2

    def test_save_creates_parent_dirs(self, tmp_path):
        reg = SchemaRegistry()
        s = ActionSchema(plugin="p", action="a", version="1.0", input={}, output={})
        reg.register(s)
        nested = tmp_path / "deep" / "nested" / "schemas.json"
        reg.save(nested)
        assert nested.exists()


# ── BreakingChangeDetector ────────────────────────────────────────────────────


def _make_reg(*schemas):
    reg = SchemaRegistry()
    for s in schemas:
        reg.register(s)
    return reg


class TestBreakingChangeDetector:
    def test_no_changes(self):
        s = ActionSchema(
            plugin="p", action="a", version="1.0",
            input={"x": "str"}, output={"y": "int"}
        )
        prev = _make_reg(s)
        curr = _make_reg(s)
        changes = BreakingChangeDetector(prev, curr).detect()
        assert changes == []

    def test_action_removed(self):
        s = ActionSchema(plugin="p", action="a", version="1.0", input={}, output={})
        prev = _make_reg(s)
        curr = _make_reg()
        changes = BreakingChangeDetector(prev, curr).detect()
        assert len(changes) == 1
        assert changes[0].kind == "action_removed"
        assert changes[0].plugin == "p"
        assert changes[0].action == "a"

    def test_input_field_removed(self):
        prev_s = ActionSchema(
            plugin="p", action="a", version="1.0",
            input={"email": "str", "password": "str"}, output={}
        )
        curr_s = ActionSchema(
            plugin="p", action="a", version="1.1",
            input={"email": "str"}, output={}
        )
        changes = BreakingChangeDetector(_make_reg(prev_s), _make_reg(curr_s)).detect()
        field_removed = [c for c in changes if c.kind == "field_removed"]
        assert len(field_removed) == 1
        assert field_removed[0].field == "password"
        assert field_removed[0].location == "input"

    def test_input_type_changed(self):
        prev_s = ActionSchema(
            plugin="p", action="a", version="1.0",
            input={"age": "int"}, output={}
        )
        curr_s = ActionSchema(
            plugin="p", action="a", version="1.1",
            input={"age": "str"}, output={}
        )
        changes = BreakingChangeDetector(_make_reg(prev_s), _make_reg(curr_s)).detect()
        type_changed = [c for c in changes if c.kind == "type_changed"]
        assert len(type_changed) == 1
        assert type_changed[0].field == "age"
        assert type_changed[0].old_value == "int"
        assert type_changed[0].new_value == "str"

    def test_output_field_removed(self):
        prev_s = ActionSchema(
            plugin="p", action="a", version="1.0",
            input={}, output={"token": "str", "expires": "int"}
        )
        curr_s = ActionSchema(
            plugin="p", action="a", version="1.1",
            input={}, output={"token": "str"}
        )
        changes = BreakingChangeDetector(_make_reg(prev_s), _make_reg(curr_s)).detect()
        output_removed = [c for c in changes if c.kind == "field_removed" and c.location == "output"]
        assert len(output_removed) == 1
        assert output_removed[0].field == "expires"

    def test_explicit_breaking_since(self):
        prev_s = ActionSchema(plugin="p", action="a", version="1.5", input={}, output={})
        curr_s = ActionSchema(
            plugin="p", action="a", version="2.0",
            input={}, output={},
            breaking_since="2.0.0"
        )
        changes = BreakingChangeDetector(_make_reg(prev_s), _make_reg(curr_s)).detect()
        explicit = [c for c in changes if c.kind == "explicit"]
        assert len(explicit) == 1

    def test_breaking_since_not_triggered_when_old_version_newer(self):
        prev_s = ActionSchema(plugin="p", action="a", version="3.0", input={}, output={})
        curr_s = ActionSchema(
            plugin="p", action="a", version="3.1",
            input={}, output={},
            breaking_since="2.0.0"
        )
        changes = BreakingChangeDetector(_make_reg(prev_s), _make_reg(curr_s)).detect()
        explicit = [c for c in changes if c.kind == "explicit"]
        assert len(explicit) == 0

    def test_plugin_filter(self):
        s_auth = ActionSchema(plugin="auth", action="login", version="1.0", input={}, output={})
        s_shop = ActionSchema(plugin="shop", action="buy", version="1.0", input={}, output={})
        prev = _make_reg(s_auth, s_shop)
        curr = _make_reg()
        changes = BreakingChangeDetector(prev, curr, plugin_filter="auth").detect()
        assert all(c.plugin == "auth" for c in changes)
        assert len(changes) == 1

    def test_str_representation(self):
        c = BreakingChange(
            plugin="p", action="a", kind="field_removed",
            field="x", location="input",
            old_value="str", new_value=None,
            message="field x removed"
        )
        s = str(c)
        assert "p:a" in s
        assert "field x removed" in s

    def test_str_no_field(self):
        c = BreakingChange(
            plugin="p", action="a", kind="action_removed",
            field=None, location="action",
            old_value="1.0", new_value=None,
            message="Action supprimée"
        )
        s = str(c)
        assert "p:a" in s

    def test_version_gt(self):
        assert BreakingChangeDetector._version_gt("2.0.0", "1.9.9") is True
        assert BreakingChangeDetector._version_gt("1.0.0", "2.0.0") is False
        assert BreakingChangeDetector._version_gt("1.0.0", "1.0.0") is False
        assert BreakingChangeDetector._version_gt("invalid", "1.0") is False

    def test_output_type_not_breaking(self):
        """Adding new output fields is non-breaking — no changes expected."""
        prev_s = ActionSchema(plugin="p", action="a", version="1.0", input={}, output={"x": "str"})
        curr_s = ActionSchema(
            plugin="p", action="a", version="1.1",
            input={}, output={"x": "str", "y": "int"}
        )
        changes = BreakingChangeDetector(_make_reg(prev_s), _make_reg(curr_s)).detect()
        assert changes == []
