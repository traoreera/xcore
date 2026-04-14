"""
Flask Adapter for XCore.
Provides a Blueprint for system routes and handles plugin routes for Flask applications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .auth_utils import hash_key, verify_api_key, run_sync

try:
    from flask import Blueprint, abort, jsonify, request
except ImportError:
    # Flask is optional
    Blueprint = Any
    request = Any
    jsonify = Any
    abort = Any

if TYPE_CHECKING:
    from ..observability import HealthChecker, MetricsRegistry
    from ..runtime.supervisor import PluginSupervisor


def build_flask_blueprint(
    supervisor: PluginSupervisor,
    secret_key: bytes,
    server_key: bytes,
    server_key_iterations: int = 100000,
    prefix: str = "",
    metrics_registry: MetricsRegistry | None = None,
    health_checker: HealthChecker | None = None,
) -> Blueprint:
    """
    Build a Flask Blueprint capturing the supervisor.
    """
    if Blueprint is Any:
        raise ImportError("Flask is required to use build_flask_blueprint")

    bp = Blueprint("xcore_system", __name__, url_prefix=f"{prefix}/ipc")

    stored_hash = hash_key(secret_key, server_key, server_key_iterations)

    @bp.before_request
    def check_auth():
        api_key = request.headers.get("X-Plugin-Key")
        if not verify_api_key(api_key, stored_hash, server_key, server_key_iterations):
            abort(401, description="Unauthorized")

    @bp.route("/<plugin_name>/<action>", methods=["POST"])
    def call_plugin(plugin_name: str, action: str):
        payload = request.json.get("payload", {}) if request.is_json else {}
        result = run_sync(supervisor.call(plugin_name, action, payload))

        if not result:
            abort(500, description="Invalid supervisor response")

        if result.get("status") == "error" and result.get("code") == "not_found":
            abort(404, description=result.get("msg", "Plugin not found"))

        return jsonify(
            {
                "status": result.get("status", "ok"),
                "plugin": plugin_name,
                "action": action,
                "result": result,
            }
        )

    @bp.route("/status", methods=["GET"])
    def plugins_status():
        return jsonify(supervisor.status())

    @bp.route("/<plugin_name>/reload", methods=["POST"])
    def reload_plugin(plugin_name: str):
        run_sync(supervisor.reload(plugin_name))
        return jsonify({"status": "ok", "msg": f"Plugin '{plugin_name}' reloaded"})

    @bp.route("/<plugin_name>/load", methods=["POST"])
    def load_plugin(plugin_name: str):
        run_sync(supervisor.load(plugin_name))
        return jsonify({"status": "ok", "msg": f"Plugin '{plugin_name}' loaded"})

    @bp.route("/<plugin_name>/unload", methods=["DELETE"])
    def unload_plugin(plugin_name: str):
        run_sync(supervisor.unload(plugin_name))
        return jsonify({"status": "ok", "msg": f"Plugin '{plugin_name}' unloaded"})

    @bp.route("/health", methods=["GET"])
    def health_check():
        if health_checker is None:
            return jsonify({"status": "healthy", "checks": {}})
        res = run_sync(health_checker.run_all())
        return jsonify(res)

    @bp.route("/metrics", methods=["GET"])
    def metrics_snapshot():
        if metrics_registry is None:
            return jsonify({})
        return jsonify(metrics_registry.snapshot())

    return bp
