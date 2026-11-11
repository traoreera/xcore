"""
yamlio.py — la lecture YAML du noyau, avec le loader C quand il est là (#305, point 4).

`yaml.safe_load` passe par le loader écrit en PYTHON, même quand PyYAML est compilé avec libyaml
(`yaml.__with_libyaml__`). Sur un manifeste de plugin réel, mesuré : **3,5 ms → 0,37 ms (×9,5)**
en passant à `CSafeLoader`. Le noyau lit un manifeste par plugin au démarrage, et le worker sandbox
relit le sien à chaque recyclage : c'est du temps de démarrage pur.

`CSafeLoader` a exactement la sûreté de `SafeLoader` (aucune construction d'objet arbitraire) ; la
seule différence est l'implémentation. Il n'est pas garanti présent (roue sans libyaml, PyYAML
installé depuis les sources) : on retombe alors sur `SafeLoader`, sans rien dire — ce n'est pas une
anomalie, juste une installation plus lente.

Module FEUILLE, sans aucun import d'xcore : le worker sandbox doit garder son jeu d'imports minimal
(#306), et `xcore/kernel/__init__.py` est vide.
"""

from __future__ import annotations

from typing import IO, Any

import yaml

try:  # pragma: no cover - dépend de la façon dont PyYAML a été installé
    from yaml import CSafeLoader as _Loader
except ImportError:  # pragma: no cover
    from yaml import SafeLoader as _Loader  # type: ignore[assignment]

#: Vrai quand le loader C est utilisé (lisible par un test ou un diagnostic).
FAST = _Loader.__name__ == "CSafeLoader"

__all__ = ["FAST", "safe_load"]


def safe_load(stream: str | bytes | IO[str] | IO[bytes]) -> Any:
    """Comme `yaml.safe_load`, mais par le loader C quand il est disponible."""
    return yaml.load(stream, Loader=_Loader)
