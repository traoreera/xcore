"""
Tests for StateMachine.
"""

import pytest

from xcore.kernel.runtime.state_machine import (InvalidTransition, PluginState,
                                                StateMachine)


class TestPluginState:
    """Test PluginState enum."""

    def test_states_exist(self):
        """Test all expected states exist."""
        assert PluginState.UNLOADED == "unloaded"
        assert PluginState.LOADING == "loading"
        assert PluginState.READY == "ready"
        assert PluginState.UNLOADING == "unloading"
        assert PluginState.RELOADING == "reloading"
        assert PluginState.FAILED == "failed"


class TestStateMachine:
    """Test StateMachine class."""

    @pytest.fixture
    def sm(self):
        """Create a StateMachine instance."""
        return StateMachine("test_plugin")

    def test_initial_state(self, sm):
        """Test initial state is UNLOADED."""
        assert sm.state == PluginState.UNLOADED

    def test_is_ready(self, sm):
        """Test is_ready property."""
        assert sm.is_ready is False

        sm.transition("load")
        sm.transition("ok")
        assert sm.is_ready is True

    def test_is_failed(self, sm):
        """Test is_failed property."""
        assert sm.is_failed is False

        sm.transition("load")
        sm.transition("error")
        assert sm.is_failed is True

    def test_is_available(self, sm):
        """Test is_available property."""
        assert sm.is_available is False

        # READY state
        sm.transition("load")
        sm.transition("ok")
        assert sm.is_available is True

        # Back to UNLOADED
        sm.transition("unload")
        sm.transition("ok")
        assert sm.is_available is False

    def test_load_transition(self, sm):
        """Test load transition."""
        new_state = sm.transition("load")
        assert new_state == PluginState.LOADING
        assert sm.state == PluginState.LOADING

    def test_load_ok_sequence(self, sm):
        """Test full load sequence."""
        sm.transition("load")
        sm.transition("ok")
        assert sm.state == PluginState.READY

    def test_load_error_sequence(self, sm):
        """Test load error sequence."""
        sm.transition("load")
        sm.transition("error")
        assert sm.state == PluginState.FAILED

    def test_unload_sequence(self, sm):
        """Test unload sequence."""
        # Load first
        sm.transition("load")
        sm.transition("ok")

        # Then unload
        sm.transition("unload")
        assert sm.state == PluginState.UNLOADING

        sm.transition("ok")
        assert sm.state == PluginState.UNLOADED

    def test_reload_sequence(self, sm):
        """Test reload sequence."""
        # Load first
        sm.transition("load")
        sm.transition("ok")

        # Then reload
        sm.transition("reload")
        assert sm.state == PluginState.RELOADING

        sm.transition("ok")
        assert sm.state == PluginState.READY

    def test_invalid_transition(self, sm):
        """Test invalid transition raises exception."""
        with pytest.raises(InvalidTransition) as exc_info:
            sm.transition("invalid_event")

        assert "invalid_event" in str(exc_info.value)
        assert "unloaded" in str(exc_info.value)

    def test_transition_from_failed(self, sm):
        """Test transitions from FAILED state."""
        sm.transition("load")
        sm.transition("error")
        assert sm.state == PluginState.FAILED

        # From FAILED, only reset is valid
        with pytest.raises(InvalidTransition):
            sm.transition("load")

        sm.transition("reset")
        assert sm.state == PluginState.UNLOADED

    def test_callback_on_change(self):
        """Test on_change callback."""
        callbacks = []

        def on_change(old, new):
            callbacks.append((old, new))

        sm = StateMachine("test_plugin", on_change=on_change)
        sm.transition("load")
        sm.transition("ok")

        assert len(callbacks) == 2
        assert callbacks[0] == (PluginState.UNLOADED, PluginState.LOADING)
        assert callbacks[1] == (PluginState.LOADING, PluginState.READY)

    def test_force_state(self, sm):
        """Test force method."""
        sm.force(PluginState.READY)
        assert sm.state == PluginState.READY
        assert sm.is_ready is True

    def test_repr(self, sm):
        """Test __repr__ method."""
        repr_str = repr(sm)
        assert "test_plugin" in repr_str
        assert "unloaded" in repr_str


class TestStateMachineComplexTransitions:
    """Test complex state transition scenarios."""

    def test_recovery_path(self):
        """Test recovery from failed state."""
        sm = StateMachine("test")
        sm.transition("load")
        sm.transition("error")
        assert sm.state == PluginState.FAILED

        sm.transition("reset")
        sm.transition("load")
        sm.transition("ok")
        assert sm.state == PluginState.READY

    def test_reload_with_error(self):
        """Test reload that fails."""
        sm = StateMachine("test")
        sm.transition("load")
        sm.transition("ok")
        sm.transition("reload")
        sm.transition("error")

        assert sm.state == PluginState.FAILED
