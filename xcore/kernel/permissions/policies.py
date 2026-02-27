"""
policies.py — Modèle de politiques d'accès pour les plugins.

Chaque plugin déclare dans son manifeste un bloc `permissions` :

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

Les politiques sont évaluées dans l'ordre ; la première correspondance gagne.
Sans règle → deny par défaut (fail-closed).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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

    def matches(self, resource: str, action: str) -> bool:
        resource_match = fnmatch.fnmatch(resource, self.resource)
        action_match = "*" in self.actions or action in self.actions
        return resource_match and action_match

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
    Ensemble ordonné de politiques pour un plugin.
    Première correspondance gagne ; sinon → DENY.
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
        """Politique permissive — pour usage interne / tests uniquement."""
        return cls(
            plugin_name=plugin_name,
            policies=[Policy(resource="*", actions=["*"], effect=PolicyEffect.ALLOW)],
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
