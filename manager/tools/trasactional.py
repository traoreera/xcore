import time
from functools import wraps

from manager.plManager import logger


class Transactions:

    @staticmethod
    def transactional(func):
        """
        Décorateur pour encapsuler proprement commit/rollback.
        Si une exception survient → rollback et log propre.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            """
            Wrapper pour encapsuler proprement commit/rollback.
            Si une exception survient → rollback et log propre.
            """
            start_time = time.time()

            try:
                result = func(self, *args, **kwargs)
                self.db.commit()
                logger.info(f"✅ Transaction successful in {func.__name__}")
                exec_time = (time.time() - start_time) * 1000
                if exec_time > 1000:  # Plus d'1 seconde
                    logger.warning(
                        f"⏱️  {func.__name__} executed in {exec_time:.2f} ms (slow performance)"
                    )
                else:
                    logger.info(f"⏱️  {func.__name__} executed in {exec_time:.2f} ms")

                return result
            except Exception as e:
                self.db.rollback()
                logger.error(f"❌ Transaction failed in {func.__name__}: {e}")
                return {"type": "error", "msg": str(e)}

        return wrapper
