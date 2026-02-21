import logging
import time
from functools import wraps
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExceptionResponse(BaseModel):
    type: str
    msg: str
    # ✅ Fix 3a : était str non-nullable → ValidationError si None
    extension: Optional[str] = None


class Error:

    @staticmethod
    def exception_handler(func, **kwargs):

        @wraps(func)
        def wrapper(*args, **kwargs):
            now = (
                time.time()
            )  # ✅ Fix 3b : now était capturé à la définition du décorateur,
            try:  # pas à l'appel → tous les timings étaient faux
                result = func(*args, **kwargs)
                time_end = time.time()
                logger.info(f" {func.__name__} executed in {time_end - now:.4f}s")
                return result

            except Exception as e:
                time_end = time.time()
                logger.error(f"Error in {func.__name__}: {e}")
                logger.exception(e)
                logger.info(
                    f" {func.__name__} executed in {time_end - now:.4f}s with error."
                )
                return {"type": "error", "msg": str(e)}

        return wrapper

    @staticmethod
    def __info(msg: str, extension: str | None = None) -> ExceptionResponse:
        return ExceptionResponse(type="info", msg=msg, extension=extension)

    @staticmethod
    def __warning(msg: str, extension: str | None = None) -> ExceptionResponse:
        # ✅ Fix 3c : retournait type="info" au lieu de "warning"
        return ExceptionResponse(type="warning", msg=msg, extension=extension)

    @staticmethod
    def __error(msg: str, extension: str | None = None) -> ExceptionResponse:
        # ✅ Fix 3c : retournait type="info" au lieu de "error"
        # ✅ Fix 3d : avait `self` en premier arg alors que c'est un @staticmethod → crash à l'appel
        return ExceptionResponse(type="error", msg=msg, extension=extension)

    @staticmethod
    def Exception_Response(
        msg: str, type: str = "error", extension: str | None = None
    ) -> ExceptionResponse:

        mapper = {
            "info": Error._Error__info,
            "warning": Error._Error__warning,
            "error": Error._Error__error,
        }

        handler = mapper.get(type)
        if handler is None:
            raise ValueError(f"Type inconnu : {type!r}. Valeurs : info, warning, error")
        return handler(msg, extension)
