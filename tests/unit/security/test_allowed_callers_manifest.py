"""allowed_callers déclaré dans plugin.yaml doit atteindre IPCAuthMiddleware.

Les tests IPC existants posent `manifest.allowed_callers` sur un MagicMock : ils
ne détectent donc pas un PluginManifest qui n'aurait plus le champ (la valeur
finissait dans `extra`, et tout appel IPC était refusé avec enforce_ipc=true).
Ici le manifest vient du vrai chargement d'un plugin.yaml.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from xcore.kernel.runtime.middlewares.ipc_auth import IPCAuthMiddleware
from xcore.kernel.security.validation import ManifestValidator


def _load(tmp_path, extra_yaml: str):
    (tmp_path / "plugin.yaml").write_text(
        "name: target\nversion: 1.0.0\nexecution_mode: trusted\n" + extra_yaml
    )
    manifest, _, _ = ManifestValidator().load_and_validate(tmp_path)
    return manifest


async def _call(manifest, caller):
    loader = MagicMock()
    loader.get_manifest.return_value = manifest
    next_call = AsyncMock(return_value={"status": "ok"})
    result = await IPCAuthMiddleware(loader, enforce=True)(
        "target", "action", {}, next_call, MagicMock(), caller=caller
    )
    return result, next_call


def test_allowed_callers_est_un_champ_du_manifest_et_non_extra(tmp_path):
    manifest = _load(tmp_path, "allowed_callers: ['sales', 'pos']\n")
    assert manifest.allowed_callers == ["sales", "pos"]
    assert "allowed_callers" not in manifest.extra


def test_allowed_callers_absent_vaut_liste_vide(tmp_path):
    assert _load(tmp_path, "").allowed_callers == []


async def test_wildcard_declare_dans_le_yaml_autorise(tmp_path):
    result, next_call = await _call(_load(tmp_path, "allowed_callers: ['*']\n"), "anyone")
    assert result["status"] == "ok"
    next_call.assert_awaited_once()


async def test_caller_liste_autorise_et_autre_refuse(tmp_path):
    manifest = _load(tmp_path, "allowed_callers: ['sales']\n")
    ok_result, _ = await _call(manifest, "sales")
    assert ok_result["status"] == "ok"
    denied, next_call = await _call(manifest, "intruder")
    assert denied["code"] == "ipc_denied"
    next_call.assert_not_called()


async def test_sans_declaration_deny_by_default(tmp_path):
    denied, next_call = await _call(_load(tmp_path, ""), "sales")
    assert denied["code"] == "ipc_denied"
    next_call.assert_not_called()
