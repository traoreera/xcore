
import asyncio
import time
from typing import Callable, List

# Simulated Middleware
class Middleware:
    async def __call__(self, plugin_name, action, payload, next_call, *, handler=None, **kwargs) -> dict:
        return await next_call(plugin_name, action, payload, handler=handler, **kwargs)

# Current Implementation
class MiddlewarePipelineOriginal:
    def __init__(self, middlewares: List[Middleware], final_handler: Callable):
        self._middlewares = middlewares
        self._final_handler = final_handler

    async def execute(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        *,
        handler=None,
        **kwargs
    ) -> dict:
        async def _chain(index: int, p_name: str, act: str, pay: dict, h, **kw) -> dict:
            if index < len(self._middlewares):
                middleware = self._middlewares[index]
                # In xcore/kernel/runtime/middleware.py:
                # lambda pn, a, pl, **k: _chain(index + 1, pn, a, pl, h, **k)
                # It doesn't pass h as a keyword argument to _chain, but as a positional argument.
                # BUT the lambda itself might receive handler in **k if some middleware calls next_call(..., handler=h)

                def next_step(pn, a, pl, **k):
                    # Simulate what happens in original code:
                    # If handler is in k, it will be passed to _chain which already has h
                    if 'handler' in k:
                        # This is where the error comes from if middleware does next_call(..., handler=...)
                        # The original code doesn't seem to account for this or it works because of how it's called.
                        del k['handler']
                    return _chain(index + 1, pn, a, pl, h, **k)

                return await middleware(
                    p_name,
                    act,
                    pay,
                    next_step,
                    handler=h,
                    **kw
                )
            return await self._final_handler(p_name, act, pay, handler=h, **kw)

        return await _chain(0, plugin_name, action, payload, handler, **kwargs)

# Optimized Implementation
class MiddlewarePipelineOptimized:
    def __init__(self, middlewares: List[Middleware], final_handler: Callable):
        self._middlewares = middlewares
        self._final_handler = final_handler
        self._compiled_chain = self._build_chain()

    def _build_chain(self):
        handler = self._final_handler
        for middleware in reversed(self._middlewares):
            handler = self._bind(middleware, handler)
        return handler

    def _bind(self, middleware, next_step):
        async def wrapper(plugin_name, action, payload, *, handler=None, **kwargs):
            return await middleware(plugin_name, action, payload, next_step, handler=handler, **kwargs)
        return wrapper

    async def execute(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        *,
        handler=None,
        **kwargs
    ) -> dict:
        return await self._compiled_chain(plugin_name, action, payload, handler=handler, **kwargs)

async def final_handler(plugin_name, action, payload, *, handler=None, **kwargs):
    return {"status": "ok"}

async def run_bench():
    middlewares = [Middleware() for _ in range(5)]

    pipe_orig = MiddlewarePipelineOriginal(middlewares, final_handler)
    pipe_opt = MiddlewarePipelineOptimized(middlewares, final_handler)

    iterations = 100000

    # Warmup
    for _ in range(100):
        await pipe_orig.execute("test", "ping", {}, handler="some_handler")
        await pipe_opt.execute("test", "ping", {}, handler="some_handler")

    print(f"Running {iterations} iterations...")

    start = time.monotonic()
    for _ in range(iterations):
        await pipe_orig.execute("test", "ping", {}, handler="some_handler")
    end = time.monotonic()
    orig_time = end - start
    print(f"Original: {orig_time:.4f}s ({orig_time/iterations*1e6:.2f} µs/call)")

    start = time.monotonic()
    for _ in range(iterations):
        await pipe_opt.execute("test", "ping", {}, handler="some_handler")
    end = time.monotonic()
    opt_time = end - start
    print(f"Optimized: {opt_time:.4f}s ({opt_time/iterations*1e6:.2f} µs/call)")

    improvement = (orig_time - opt_time) / orig_time * 100
    print(f"Improvement: {improvement:.2f}%")

if __name__ == "__main__":
    asyncio.run(run_bench())
