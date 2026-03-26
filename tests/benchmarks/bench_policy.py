
import time
import fnmatch
from dataclasses import dataclass
from enum import Enum

class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"

@dataclass
class Policy:
    resource: str
    actions: list[str]
    effect: PolicyEffect = PolicyEffect.ALLOW

    def matches_original(self, resource: str, action: str) -> bool:
        resource_match = fnmatch.fnmatch(resource, self.resource)
        action_match = "*" in self.actions or action in self.actions
        return resource_match and action_match

    def matches_optimized(self, resource: str, action: str) -> bool:
        # Check action first (list lookup is fast)
        if "*" not in self.actions and action not in self.actions:
            return False
        # Then check resource (fnmatch is slow)
        return fnmatch.fnmatch(resource, self.resource)

def benchmark():
    policy = Policy(resource="db.*", actions=["read", "write"])
    iterations = 1000000

    print(f"Benchmarking with {iterations} iterations...")

    # Case 1: Action doesn't match (Expected fast exit in optimized)
    resource = "db.users"
    action = "delete"

    start = time.time()
    for _ in range(iterations):
        policy.matches_original(resource, action)
    end = time.time()
    print(f"Original (Action mismatch): {end - start:.4f}s")

    start = time.time()
    for _ in range(iterations):
        policy.matches_optimized(resource, action)
    end = time.time()
    print(f"Optimized (Action mismatch): {end - start:.4f}s")

    # Case 2: Action matches, Resource doesn't match
    resource = "other.resource"
    action = "read"

    start = time.time()
    for _ in range(iterations):
        policy.matches_original(resource, action)
    end = time.time()
    print(f"Original (Resource mismatch): {end - start:.4f}s")

    start = time.time()
    for _ in range(iterations):
        policy.matches_optimized(resource, action)
    end = time.time()
    print(f"Optimized (Resource mismatch): {end - start:.4f}s")

    # Case 3: Both match
    resource = "db.users"
    action = "read"

    start = time.time()
    for _ in range(iterations):
        policy.matches_original(resource, action)
    end = time.time()
    print(f"Original (Full match): {end - start:.4f}s")

    start = time.time()
    for _ in range(iterations):
        policy.matches_optimized(resource, action)
    end = time.time()
    print(f"Optimized (Full match): {end - start:.4f}s")

if __name__ == "__main__":
    benchmark()
