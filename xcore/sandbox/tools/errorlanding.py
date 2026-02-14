import time
from functools import wraps
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExceptionResponse(BaseModel):
    type: str
    msg: str
    extension: str


class Error:

    @staticmethod
    def exception_handler(func, **kwargs):

        now = time.time()

        @wraps(func)
        def wrapper(*args, **kwargs):

            try:
                result = func(*args, **kwargs)
                time_end = time.time()
                logger.info(f" {func.__name__} executed in {time_end - now:.2f} ms")
                return result

            except Exception as e:
                time_end = time.time()
                logger.error(f"Error in {func.__name__}: {e}")
                logger.exception(e)
                logger.info(
                    f" {func.__name__} executed in {time_end - now:.2f} ms with error."
                )
                return {"type": "error", "msg": str(e)}

        return wrapper

    @staticmethod
    def __info(msg, extension: str = None) -> ExceptionResponse:
        return ExceptionResponse(type="info", msg=msg, extension=extension)

    @staticmethod
    def __warning(msg, extension: str = None):
        return ExceptionResponse(type="info", msg=msg, extension=extension)

    @staticmethod
    def __error(self, msg, extension: str = None):
        return ExceptionResponse(type="info", msg=msg, extension=extension)

    @staticmethod
    def Exception_Response(
        msg, type="error", extension: str = None
    ) -> ExceptionResponse:

        mapper = {
            "info": Error.__info,
            "warning": Error.__warning,
            "error": Error.__error,
        }

        return mapper[type](msg, extension)