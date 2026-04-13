"""
--- Plugin Access Policy Template ---
Each plugin declares a `permissions` block in its manifest:
permissions:
- resource: "db.*"
actions: ["read", "write"]
effect: allow
- resource: "cache.*"
actions: ["read"]
effect: allow
- resource: "os.*"
actions: ["*"]
effect: deny
Policies are evaluated in order; the first match wins.
No rule → default is deny (fail-closed).
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Pattern


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class Policy:
    """
    Une règle d'accès : resource × actions → effect.

    resource : glob pattern  ex. "db.*", "cache.get", "*"
    actions  : liste de verbes ou ["*"]  ex. ["read", "write"]
    effect   : allow | deny
    """

    resource: str
    actions: list[str]
    effect: PolicyEffect = PolicyEffect.ALLOW

    # Fields pre-calculated for performance
    _actions_set: set[str] = field(init=False, repr=False)
    _regex: Pattern | None = field(init=False, repr=False)
    _is_wildcard: bool = field(init=False, repr=False)
    _has_star_action: bool = field(init=False, repr=False)

    def __post_init__(self):
        """Pre-calculate values to speed up the 'matches' hot path."""
        self._actions_set = set(self.actions)
        self._has_star_action = "*" in self._actions_set

        # Determine if the resource pattern contains glob wildcards
        self._is_wildcard = any(c in self.resource for c in "*?[]")

        if self._is_wildcard:
            # Compile regex once to avoid fnmatch overhead in the hot path
            # fnmatch.translate converts a glob pattern to a regex string
            self._regex = re.compile(fnmatch.translate(self.resource))
        else:
            self._regex = None

    def matches(self, resource: str, action: str) -> bool:
        """
        Check if the rule matches the given resource and action.
        Optimized to use pre-calculated sets and regex.
        """
        # 1. Action check: O(1) set lookup is much faster than list iteration
        if not self._has_star_action and action not in self._actions_set:
            return False

        # 2. Resource check:
        # - If not a wildcard, simple string comparison is fastest
        if not self._is_wildcard:
            return resource == self.resource

        # - If wildcard, use pre-compiled regex
        return bool(self._regex.match(resource))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Policy":
        effect_raw = d.get("effect", "allow").lower()
        try:
            effect = PolicyEffect(effect_raw)
        except ValueError:
            raise ValueError(
                f"effect invalide : {effect_raw!r}. Valeurs : allow | deny"
            )
        actions = d.get("actions", ["*"])
        if isinstance(actions, str):
            actions = [actions]
        return cls(resource=d["resource"], actions=actions, effect=effect)


@dataclass
class PolicySet:
    """
    Ordered set of policies for a plugin.
    First match wins; otherwise → DENY.
    """

    plugin_name: str
    policies: list[Policy] = field(default_factory=list)

    def evaluate(self, resource: str, action: str) -> PolicyEffect:
        for policy in self.policies:
            if policy.matches(resource, action):
                return policy.effect
        return PolicyEffect.DENY  # fail-closed

    def allows(self, resource: str, action: str) -> bool:
        return self.evaluate(resource, action) == PolicyEffect.ALLOW

    @classmethod
    def from_list(cls, plugin_name: str, raw_policies: list[dict]) -> "PolicySet":
        policies = [Policy.from_dict(p) for p in raw_policies]
        return cls(plugin_name=plugin_name, policies=policies)

    @classmethod
    def allow_all(cls, plugin_name: str) -> "PolicySet":
        """Permissive policy — for internal use / testing only."""
        return cls(
            plugin_name=plugin_name,
            policies=[Policy(resource="*", actions=["*"],
                             effect=PolicyEffect.ALLOW)],
        )

    @classmethod
    def deny_all(cls, plugin_name: str) -> "PolicySet":
        return cls(plugin_name=plugin_name, policies=[])

    def to_list(self) -> list[dict]:
        return [
            {"resource": p.resource, "actions": p.actions, "effect": p.effect.value}
            for p in self.policies
        ]

    def __repr__(self) -> str:
        return f"<PolicySet plugin='{self.plugin_name}' rules={len(self.policies)}>"
