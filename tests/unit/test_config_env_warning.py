"""Une variable ${VAR} absente se résout en chaîne vide avec un avertissement
correctement formaté (champs structurés, pas d'argument positionnel orphelin)."""

import logging

from xcore.configurations.helper import _resolve


def test_variable_absente_donne_chaine_vide_sans_erreur_de_logging(monkeypatch):
    erreurs: list[BaseException] = []
    monkeypatch.setattr(logging, "raiseExceptions", True)
    monkeypatch.setattr(
        logging.Handler,
        "handleError",
        lambda self, record: erreurs.append(record),
    )
    monkeypatch.delenv("XCORE_TEST_VAR_ABSENTE", raising=False)

    out = _resolve({"k": "${XCORE_TEST_VAR_ABSENTE}", "l": ["a-${XCORE_TEST_VAR_ABSENTE}"]})

    assert out == {"k": "", "l": ["a-"]}
    assert erreurs == [], "le log d'avertissement ne doit pas lever d'erreur de formatage"


def test_variable_definie_est_substituee(monkeypatch):
    monkeypatch.setenv("XCORE_TEST_VAR_OK", "valeur")
    assert _resolve("pre-${XCORE_TEST_VAR_OK}-post") == "pre-valeur-post"
