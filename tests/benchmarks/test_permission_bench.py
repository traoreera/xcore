import fnmatch
import timeit
from dataclasses import dataclass, field
from enum import Enum


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class Policy:
    resource: str
    actions: list[str]
    effect: PolicyEffect = PolicyEffect.ALLOW

    def matches(self, resource: str, action: str) -> bool:
        resource_match = fnmatch.fnmatch(resource, self.resource)
        action_match = "*" in self.actions or action in self.actions
        return resource_match and action_match


@dataclass
class PolicySet:
    plugin_name: str
    policies: list[Policy] = field(default_factory=list)

    def evaluate(self, resource: str, action: str) -> PolicyEffect:
        for policy in self.policies:
            if policy.matches(resource, action):
                return policy.effect
        return PolicyEffect.DENY


class PermissionEngine:
    def __init__(self) -> None:
        self._policies = {}
        self._audit_log = []

    def load_from_manifest(self, plugin_name, raw_permissions):
        policies = [
            Policy(p["resource"], p["actions"], PolicyEffect(p.get("effect", "allow")))
            for p in raw_permissions
        ]
        self._policies[plugin_name] = PolicySet(plugin_name, policies)

    def _evaluate(self, plugin_name: str, resource: str, action: str) -> PolicyEffect:
        ps = self._policies.get(plugin_name)
        if ps is None:
            return PolicyEffect.DENY
        return ps.evaluate(resource, action)

    def _audit(self, plugin_name, resource, action, effect):
        entry = {
            "plugin": plugin_name,
            "resource": resource,
            "action": action,
            "effect": effect.value,
        }
        self._audit_log.append(entry)

    def check(self, plugin_name, resource, action):
        effect = self._evaluate(plugin_name, resource, action)
        self._audit(plugin_name, resource, action, effect)
        if effect == PolicyEffect.DENY:
            pass  # Simplified

    def allows(self, plugin_name: str, resource: str, action: str) -> bool:
        try:
            self.check(plugin_name, resource, action)
            # This is a bit simplified compared to original but should show the overhead of _evaluate
            return True
        except:
            return False


class PermissionEngineOptimized(PermissionEngine):
    def __init__(self) -> None:
        super().__init__()
        self._cache = {}

    def _evaluate(self, plugin_name: str, resource: str, action: str) -> PolicyEffect:
        key = (plugin_name, resource, action)
        if key in self._cache:
            return self._cache[key]

        result = super()._evaluate(plugin_name, resource, action)
        self._cache[key] = result
        return result


def benchmark_permissions():
    engine = PermissionEngine()
    engine_opt = PermissionEngineOptimized()

    permissions = [
        {"resource": "db.users.*", "actions": ["read"], "effect": "allow"},
        {"resource": "db.admin.*", "actions": ["*"], "effect": "deny"},
        {"resource": "cache.*", "actions": ["read", "write"], "effect": "allow"},
        {"resource": "fs.tmp.*", "actions": ["write"], "effect": "allow"},
        {"resource": "api.v1.*", "actions": ["call"], "effect": "allow"},
    ]
    engine.load_from_manifest("test_plugin", permissions)
    engine_opt.load_from_manifest("test_plugin", permissions)

    resources_actions = [
        ("db.users.profile", "read"),
        ("db.admin.secrets", "read"),
        ("cache.data", "write"),
        ("fs.tmp.file1", "write"),
        ("api.v1.login", "call"),
        ("unknown.resource", "read"),
    ]

    def run_benchmark(e):
        for res, act in resources_actions:
            e.allows("test_plugin", res, act)

    iterations = 10000

    t1 = timeit.Timer(lambda: run_benchmark(engine)).timeit(number=iterations)
    print(f"Original - Time for {iterations} iterations: {t1:.4f}s")

    t2 = timeit.Timer(lambda: run_benchmark(engine_opt)).timeit(number=iterations)
    print(f"Optimized (Cached) - Time for {iterations} iterations: {t2:.4f}s")

    improvement = (t1 - t2) / t1 * 100
    print(f"Improvement: {improvement:.2f}%")


if __name__ == "__main__":
    benchmark_permissions()
