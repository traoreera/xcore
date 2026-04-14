"""
Django Adapter for XCore.
Provides URL patterns and views for Django applications.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .auth_utils import hash_key, run_sync, verify_api_key

try:
    from django.http import HttpResponse, JsonResponse
    from django.urls import path
    from django.utils.decorators import method_decorator
    from django.views import View
    from django.views.decorators.csrf import csrf_exempt
except ImportError:
    # Django is optional
    JsonResponse = Any
    HttpResponse = Any
    View = Any
    path = Any
    csrf_exempt = lambda x: x
    method_decorator = lambda x: lambda y: y

if TYPE_CHECKING:
    from ..observability import HealthChecker, MetricsRegistry
    from ..runtime.supervisor import PluginSupervisor


def build_django_urls(
    supervisor: PluginSupervisor,
    secret_key: bytes,
    server_key: bytes,
    server_key_iterations: int = 100000,
    metrics_registry: MetricsRegistry | None = None,
    health_checker: HealthChecker | None = None,
):
    """
    Build Django URL patterns for XCore system routes.
    """
    if JsonResponse is Any:
        raise ImportError("Django is required to use build_django_urls")

    stored_hash = hash_key(secret_key, server_key, server_key_iterations)

    def verify_request(request):
        api_key = request.headers.get("X-Plugin-Key")
        return verify_api_key(api_key, stored_hash, server_key, server_key_iterations)

    @method_decorator(csrf_exempt, name="dispatch")
    class CallPluginView(View):
        def post(self, request, plugin_name, action):
            if not verify_request(request):
                return HttpResponse("Unauthorized", status=401)

            try:
                payload = json.loads(request.body).get("payload", {})
            except:
                payload = {}

            result = run_sync(supervisor.call(plugin_name, action, payload))

            if not result:
                return JsonResponse({"error": "Invalid supervisor response"}, status=500)

            if result.get("status") == "error" and result.get("code") == "not_found":
                return JsonResponse(
                    {"error": result.get("msg", "Plugin not found")}, status=404
                )

            return JsonResponse(
                {
                    "status": result.get("status", "ok"),
                    "plugin": plugin_name,
                    "action": action,
                    "result": result,
                }
            )

    @method_decorator(csrf_exempt, name="dispatch")
    class StatusView(View):
        def get(self, request):
            if not verify_request(request):
                return HttpResponse("Unauthorized", status=401)
            return JsonResponse(supervisor.status())

    @method_decorator(csrf_exempt, name="dispatch")
    class ReloadPluginView(View):
        def post(self, request, plugin_name):
            if not verify_request(request):
                return HttpResponse("Unauthorized", status=401)
            run_sync(supervisor.reload(plugin_name))
            return JsonResponse(
                {"status": "ok", "msg": f"Plugin '{plugin_name}' reloaded"}
            )

    @method_decorator(csrf_exempt, name="dispatch")
    class LoadPluginView(View):
        def post(self, request, plugin_name):
            if not verify_request(request):
                return HttpResponse("Unauthorized", status=401)
            run_sync(supervisor.load(plugin_name))
            return JsonResponse({"status": "ok", "msg": f"Plugin '{plugin_name}' loaded"})

    @method_decorator(csrf_exempt, name="dispatch")
    class UnloadPluginView(View):
        def delete(self, request, plugin_name):
            if not verify_request(request):
                return HttpResponse("Unauthorized", status=401)
            run_sync(supervisor.unload(plugin_name))
            return JsonResponse(
                {"status": "ok", "msg": f"Plugin '{plugin_name}' unloaded"}
            )

    @method_decorator(csrf_exempt, name="dispatch")
    class HealthCheckView(View):
        def get(self, request):
            if not verify_request(request):
                return HttpResponse("Unauthorized", status=401)
            if health_checker is None:
                return JsonResponse({"status": "healthy", "checks": {}})
            res = run_sync(health_checker.run_all())
            return JsonResponse(res)

    @method_decorator(csrf_exempt, name="dispatch")
    class MetricsView(View):
        def get(self, request):
            if not verify_request(request):
                return HttpResponse("Unauthorized", status=401)
            if metrics_registry is None:
                return JsonResponse({})
            return JsonResponse(metrics_registry.snapshot())

    urlpatterns = [
        path("ipc/<str:plugin_name>/<str:action>", CallPluginView.as_view()),
        path("ipc/status", StatusView.as_view()),
        path("ipc/<str:plugin_name>/reload", ReloadPluginView.as_view()),
        path("ipc/<str:plugin_name>/load", LoadPluginView.as_view()),
        path("ipc/<str:plugin_name>/unload", UnloadPluginView.as_view()),
        path("ipc/health", HealthCheckView.as_view()),
        path("ipc/metrics", MetricsView.as_view()),
    ]

    return urlpatterns
