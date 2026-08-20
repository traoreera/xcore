from typing import Callable


class RouterRegistry:
    """
    Decorators for FastAPI routers.
    this is a wrapper around FastAPI's router
    """

    @staticmethod
    def router(
        path: str,
        method: str = "GET",
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        status_code: int = 200,
        response_model=None,
        dependencies: list | None = None,  # ← FastAPI Depends() par route
        permissions: (
            list[str] | None
        ) = None,  # ← RBAC déclaratif ["admin", "read:users"]
        scopes: list[str] | None = None,
    ):

        def decorator(fn: Callable) -> Callable:
            fn._xcore_route = {
                "path": path,
                "method": method.upper(),
                "tags": tags or [],
                "summary": summary or fn.__name__.replace("_", " ").title(),
                "status_code": status_code,
                "response_model": response_model,
                "dependencies": dependencies or [],
                "permissions": permissions or [],
                "scopes": scopes or [],
            }
            return fn

        return decorator

    def get(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        status_code: int = 200,
        response_model=None,
        dependencies: list | None = None,
        permissions: list[str] | None = None,
        scopes: list[str] | None = None,
    ):
        return self.router(
            path,
            "GET",
            tags=tags,
            summary=summary,
            status_code=status_code,
            response_model=response_model,
            dependencies=dependencies,
            permissions=permissions,
            scopes=scopes,
        )

    def post(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        status_code: int = 200,
        response_model=None,
        dependencies: list | None = None,
        permissions: list[str] | None = None,
        scopes: list[str] | None = None,
    ):
        return self.router(
            path,
            "POST",
            tags=tags,
            summary=summary,
            status_code=status_code,
            response_model=response_model,
            dependencies=dependencies,
            permissions=permissions,
            scopes=scopes,
        )

    def put(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        status_code: int = 200,
        response_model=None,
        dependencies: list | None = None,
        permissions: list[str] | None = None,
        scopes: list[str] | None = None,
    ):
        return self.router(
            path,
            "PUT",
            tags=tags,
            summary=summary,
            status_code=status_code,
            response_model=response_model,
            dependencies=dependencies,
            permissions=permissions,
            scopes=scopes,
        )

    def delete(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        status_code: int = 200,
        response_model=None,
        dependencies: list | None = None,
        permissions: list[str] | None = None,
        scopes: list[str] | None = None,
    ):
        return self.router(
            path,
            "DELETE",
            tags=tags,
            summary=summary,
            status_code=status_code,
            response_model=response_model,
            dependencies=dependencies,
            permissions=permissions,
            scopes=scopes,
        )

    def patch(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        status_code: int = 200,
        response_model=None,
        dependencies: list | None = None,
        permissions: list[str] | None = None,
        scopes: list[str] | None = None,
    ):
        return self.router(
            path,
            "PATCH",
            tags=tags,
            summary=summary,
            status_code=status_code,
            response_model=response_model,
            dependencies=dependencies,
            permissions=permissions,
            scopes=scopes,
        )

    def route_instance(self, fn: Callable):  # ← FastAPI Depends() par route
        return self.router(
            fn._xcore_route["path"],
            fn._xcore_route["method"],
            tags=fn._xcore_route["tags"],
            summary=fn._xcore_route["summary"],
            status_code=fn._xcore_route["status_code"],
            response_model=fn._xcore_route["response_model"],
            dependencies=fn._xcore_route["dependencies"],
            permissions=fn._xcore_route["permissions"],
            scopes=fn._xcore_route["scopes"],
        )(fn)
