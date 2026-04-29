import pytest

from xcore.kernel.permissions.engine import PermissionEngine
from xcore.kernel.permissions.policies import Policy, PolicyEffect


@pytest.mark.benchmark(group="policy-matching")
def test_policy_match_success(benchmark):
    """Benchmark un match réussi de policy."""
    policy = Policy(resource="db.*", actions=["read", "write"])
    resource = "db.users"
    action = "read"

    result = benchmark(policy.matches, resource, action)
    assert result is True


@pytest.mark.benchmark(group="policy-matching")
def test_policy_match_failure_action(benchmark):
    """Benchmark un échec de match (action incorrecte)."""
    policy = Policy(resource="db.*", actions=["read", "write"])
    resource = "db.users"
    action = "delete"

    result = benchmark(policy.matches, resource, action)
    assert result is False


@pytest.mark.benchmark(group="policy-matching")
def test_policy_match_failure_resource(benchmark):
    """Benchmark un échec de match (ressource incorrecte)."""
    policy = Policy(resource="db.*", actions=["read", "write"])
    resource = "other.resource"
    action = "read"

    result = benchmark(policy.matches, resource, action)
    assert result is False


def run_permission_check(engine, plugin_name, resources_actions):
    for res, act in resources_actions:
        engine.allows(plugin_name, res, act)


@pytest.mark.benchmark(group="permission-engine")
def test_permission_engine_evaluation(benchmark):
    """Benchmark de l'évaluation globale par le PermissionEngine."""
    engine = PermissionEngine()
    permissions = [
        {"resource": "db.users.*", "actions": ["read"], "effect": "allow"},
        {"resource": "db.admin.*", "actions": ["*"], "effect": "deny"},
        {"resource": "cache.*", "actions": ["read", "write"], "effect": "allow"},
        {"resource": "fs.tmp.*", "actions": ["write"], "effect": "allow"},
        {"resource": "api.v1.*", "actions": ["call"], "effect": "allow"},
    ]
    engine.load_from_manifest("test_plugin", permissions)

    resources_actions = [
        ("db.users.profile", "read"),
        ("db.admin.secrets", "read"),
        ("cache.data", "write"),
        ("fs.tmp.file1", "write"),
        ("api.v1.login", "call"),
        ("unknown.resource", "read"),
    ]

    # On vide le cache avant chaque tour si nécessaire,
    # mais ici on veut tester la performance RÉELLE (incluant le cache)
    benchmark(run_permission_check, engine, "test_plugin", resources_actions)


@pytest.mark.benchmark(group="permission-engine")
def test_permission_engine_no_cache(benchmark):
    """Benchmark de l'évaluation sans cache (pire cas)."""
    engine = PermissionEngine()
    permissions = [
        {"resource": "db.users.*", "actions": ["read"], "effect": "allow"},
        {"resource": "db.admin.*", "actions": ["*"], "effect": "deny"},
        {"resource": "cache.*", "actions": ["read", "write"], "effect": "allow"},
        {"resource": "fs.tmp.*", "actions": ["write"], "effect": "allow"},
        {"resource": "api.v1.*", "actions": ["call"], "effect": "allow"},
    ]
    engine.load_from_manifest("test_plugin", permissions)

    resources_actions = [
        ("db.users.profile", "read"),
        ("db.admin.secrets", "read"),
        ("cache.data", "write"),
        ("fs.tmp.file1", "write"),
        ("api.v1.login", "call"),
        ("unknown.resource", "read"),
    ]

    def run_with_clear_cache():
        engine._cache.clear()
        run_permission_check(engine, "test_plugin", resources_actions)

    benchmark(run_with_clear_cache)
