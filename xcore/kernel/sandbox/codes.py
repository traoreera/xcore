"""
codes.py — Codes de sortie du worker sandbox.

Module FEUILLE, sans aucun import : le worker le charge par son fichier (voir
`worker._leaf`) pour ne pas exécuter les `__init__` des packages xcore, donc sans
fastapi, pydantic ni OpenTelemetry dans un process qui n'en a pas l'usage (#316).
"""

# Code de sortie d'un worker qui se recycle de lui-même parce que son plafond de
# CPU cumulé est presque atteint (EX_TEMPFAIL) — ce n'est pas un plantage : le
# SandboxProcessManager le relance sans le compter dans `max_restarts`.
RECYCLE_EXIT_CODE = 75
