"""@schema : la validation n'est appliquée que si type_response != "_" (défaut)."""

from xcore.sdk.decorators import schema


class _P:
    @schema(version="1.0", input={"qty": (int, ...)})
    async def metadata_only(self, payload: dict) -> dict:
        return {"ran": True, "payload": payload}

    @schema(version="1.0", input={"qty": (int, ...)}, type_response="dict")
    async def validated(self, payload: dict) -> dict:
        return {"ran": True, "payload": payload}


async def test_default_type_response_does_not_validate():
    # Comportement documenté (doc/sdk/api/decorators.md) : métadonnées seules.
    out = await _P().metadata_only({"qty": "not-an-int"})
    assert out == {"ran": True, "payload": {"qty": "not-an-int"}}
    assert _P.metadata_only._xcore_schema["input"] == {"qty": "int"}


async def test_type_response_dict_rejects_invalid_payload():
    out = await _P().validated({"qty": "not-an-int"})
    assert out.get("status") == "error" or out.get("code") == "validation_error"


async def test_type_response_dict_accepts_valid_payload():
    out = await _P().validated({"qty": "3"})
    assert out == {"ran": True, "payload": {"qty": 3}}
