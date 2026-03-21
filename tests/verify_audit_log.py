
from collections import deque
from xcore.kernel.permissions.engine import PermissionEngine

def test_audit_log_filtering():
    engine = PermissionEngine()
    # Fill with some data
    for i in range(10):
        engine._audit("p1", "r", "a", type('obj', (object,), {'value': 'allow'}))
    for i in range(10):
        engine._audit("p2", "r", "a", type('obj', (object,), {'value': 'allow'}))

    # Test filtering
    log_p1 = engine.audit_log(plugin_name="p1", limit=5)
    assert len(log_p1) == 5
    assert all(e["plugin"] == "p1" for e in log_p1)

    log_p2 = engine.audit_log(plugin_name="p2", limit=100)
    assert len(log_p2) == 10
    assert all(e["plugin"] == "p2" for e in log_p2)

    # Test no filtering (fix for deque slicing)
    log_all = engine.audit_log(limit=5)
    assert len(log_all) == 5
    # Should be the last 5 entries (which are p2)
    assert all(e["plugin"] == "p2" for e in log_all)

    log_all_full = engine.audit_log(limit=100)
    assert len(log_all_full) == 20

    print("Audit log manual verification PASSED")

if __name__ == "__main__":
    test_audit_log_filtering()
