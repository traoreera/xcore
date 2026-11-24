"""
service_contracts.py — Le contrat de services d'un plugin, vérifié au CHARGEMENT (#311).

`self.get_service("doctype_writer")` échoue à l'appel, pas au chargement : un plugin qui
attend un service absent (ou dont le contrat a changé) démarrait, répondait aux requêtes,
et cassait à la première écriture — en production. Le manifeste dit désormais ce qu'il
attend et ce qu'il fournit :

    # consommateur                         # fournisseur
    requires_services:                     provides_services:
      - name: doctype_writer                 - name: doctype_writer
        version: ">=2"                         version: "2.1"

et le loader refuse, avant d'exécuter une ligne du plugin, celui dont un service requis
manque ou dont la version ne satisfait pas la contrainte — avec un message qui nomme les
deux plugins. `get_service` reste tel quel : c'est le chargement qui gagne une garantie.

Ce module ne contient que des fonctions pures sur des manifestes ; c'est `PluginLoader`
qui les applique (ordre de chargement, refus, cascade).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


class ServiceContractError(Exception):
    """Un contrat de services n'est pas tenu : le plugin ne doit pas être chargé."""


@dataclass(frozen=True)
class Provider:
    """Qui fournit un service, et sous quelle version de contrat."""

    plugin: str
    version: str | None = None


def index_providers(
    manifests: Iterable[Any],
) -> tuple[dict[str, Provider], dict[str, str]]:
    """
    Construit `service → fournisseur` à partir des `provides_services` déclarés.

    Deux plugins qui déclarent le même service : le premier (ordre des manifestes) le
    garde, le second est rendu dans `conflicts` (`plugin → raison`) et sera refusé —
    laisser le dernier chargé gagner ferait dépendre le contrat de l'ordre des vagues.
    """
    providers: dict[str, Provider] = {}
    conflicts: dict[str, str] = {}
    for manifest in manifests:
        for provision in getattr(manifest, "provides_services", None) or []:
            holder = providers.get(provision.name)
            if holder is not None and holder.plugin != manifest.name:
                conflicts[manifest.name] = (
                    f"le service '{provision.name}' est déjà fourni par le plugin "
                    f"'{holder.plugin}'"
                )
                continue
            providers[provision.name] = Provider(manifest.name, provision.version)
    return providers, conflicts


def unmet_requirements(
    manifest: Any,
    providers: dict[str, Provider],
    available: Iterable[str] = (),
    refused: dict[str, str] | None = None,
) -> list[str]:
    """
    Raisons pour lesquelles `manifest` ne peut pas être chargé ([] = contrat tenu).

    `available` : services déjà présents sans fournisseur déclaré (services noyau —
    db, cache, scheduler… — et services d'un plugin qui n'a pas de `provides_services`).
    Ils n'ont pas de version : ils ne satisfont qu'une exigence sans contrainte.
    `refused` : plugins déjà écartés (`plugin → raison`) — ce qu'ils fournissent manque.
    """
    refused = refused or {}
    present = set(available)
    reasons: list[str] = []
    for req in getattr(manifest, "requires_services", None) or []:
        provider = providers.get(req.name)
        if provider is not None and provider.plugin == manifest.name:
            continue  # se requiert lui-même : sans objet
        if provider is None:
            if req.name not in present:
                reasons.append(
                    f"service requis '{req.name}' : aucun plugin ne le fournit "
                    "(provides_services) et aucun service de ce nom n'est enregistré"
                )
            elif not req.accepts(None):
                reasons.append(
                    f"service requis '{req.name}' {req.version_constraint} : il est "
                    "enregistré sans version déclarée (provides_services absent chez "
                    "son fournisseur)"
                )
            continue
        if provider.plugin in refused:
            reasons.append(
                f"service requis '{req.name}' : son fournisseur, le plugin "
                f"'{provider.plugin}', n'est pas chargé ({refused[provider.plugin]})"
            )
        elif not req.accepts(provider.version):
            reasons.append(
                f"service requis '{req.name}' {req.version_constraint} : le plugin "
                f"'{provider.plugin}' le fournit en version "
                f"{provider.version or 'non déclarée'}"
            )
    return reasons


def refuse_unsatisfied(
    manifests: list[Any], available: Iterable[str] = ()
) -> tuple[dict[str, Provider], dict[str, str]]:
    """
    Applique les contrats à un ensemble de manifestes : `(fournisseurs, refusés)`.

    Point fixe : refuser un fournisseur fait manquer ses services à ses consommateurs,
    qui sont refusés à leur tour, avec une raison qui nomme le fournisseur.
    """
    providers, refused = index_providers(manifests)
    available = set(available)
    changed = True
    while changed:
        changed = False
        for manifest in manifests:
            if manifest.name in refused:
                continue
            if reasons := unmet_requirements(manifest, providers, available, refused):
                refused[manifest.name] = " ; ".join(reasons)
                changed = True
    return providers, refused


def service_dependencies(manifest: Any, providers: dict[str, Provider]) -> set[str]:
    """Plugins à charger AVANT `manifest` parce qu'ils fournissent un service requis."""
    deps = set()
    for req in getattr(manifest, "requires_services", None) or []:
        provider = providers.get(req.name)
        if provider is not None and provider.plugin != manifest.name:
            deps.add(provider.plugin)
    return deps


def missing_provisions(manifest: Any, exported: Iterable[str]) -> list[str]:
    """Services que le manifeste déclare fournir mais que le plugin n'a pas exportés."""
    present = set(exported)
    return [
        p.name
        for p in getattr(manifest, "provides_services", None) or []
        if p.name not in present
    ]
