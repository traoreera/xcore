"""
blocking.py — Détection du code synchrone qui gèle le event loop.

Un plugin Trusted (ou un job du scheduler) s'exécute dans le thread du event loop.
Tout ce qu'il fait *entre deux `await`* — calcul CPU, I/O bloquant, `time.sleep` —
suspend l'application entière, et `asyncio.wait_for(timeout=...)` ne peut rien y
faire : le timer ne passe qu'au prochain `await`. Mesuré : un handler qui consomme
1 s de CPU sans `await` avec `timeout_seconds=0.2` rend `status: ok` au bout de
1000 ms, pas une erreur de timeout au bout de 200 ms.

`watch_blocking()` ne peut pas l'empêcher (c'est la limite du GIL + d'un loop
unique), mais le rend visible et attribuable : elle mesure chaque *pas* synchrone
de l'awaitable — le temps passé entre deux suspensions — et prévient quand il
dépasse le seuil. Pour du CPU lourd : `asyncio.to_thread`, ou le mode `sandboxed`
(un processus par plugin, donc hors du GIL et du loop principal).
"""

from __future__ import annotations

import contextlib
import inspect
import time
from typing import Any, Awaitable, Callable


class _StepWatch:
    """Awaitable transparent qui chronomètre chaque pas synchrone de l'inner."""

    __slots__ = ("_aw", "_threshold_s", "_on_block")

    def __init__(
        self,
        aw: Awaitable[Any],
        threshold_s: float,
        on_block: Callable[[float], None],
    ) -> None:
        self._aw = aw
        self._threshold_s = threshold_s
        self._on_block = on_block

    def _observe(self, start: float) -> None:
        elapsed = time.perf_counter() - start
        if elapsed >= self._threshold_s:
            # Une erreur de rapport ne doit jamais casser l'appel du plugin.
            with contextlib.suppress(Exception):
                self._on_block(elapsed)

    def __await__(self):
        it = self._aw.__await__()
        value: Any = None
        exc: BaseException | None = None
        while True:
            start = time.perf_counter()
            try:
                yielded = it.throw(exc) if exc is not None else it.send(value)
            except StopIteration as stop:
                self._observe(start)
                return stop.value
            except BaseException:
                self._observe(start)
                raise
            self._observe(start)
            exc, value = None, None
            try:
                value = yield yielded
            except GeneratorExit:
                it.close()
                raise
            except BaseException as e:  # CancelledError (timeout/cancel) inclus
                exc = e


def watch_blocking(
    aw: Awaitable[Any],
    threshold_ms: float,
    on_block: Callable[[float], None],
) -> Awaitable[Any]:
    """
    Enveloppe `aw` pour signaler (via `on_block(seconds)`) chaque pas synchrone
    d'au moins `threshold_ms`. Sans effet si le seuil est ≤ 0 ou si `aw` n'est
    pas un awaitable.
    """
    if threshold_ms <= 0 or not inspect.isawaitable(aw):
        return aw
    return _StepWatch(aw, threshold_ms / 1000.0, on_block)
