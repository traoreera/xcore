import time 
from functools import wraps
from manager.plManager import logger



class Error:

    @staticmethod
    def exception_handler(func):

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
                logger.info(f" {func.__name__} executed in {time_end - now:.2f} ms with error.")
                return {"type": "error", "msg": str(e)}

        return wrapper
