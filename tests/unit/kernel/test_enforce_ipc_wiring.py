"""enforce_ipc / tenancy racine doivent atteindre le superviseur (vraie config)."""

from types import SimpleNamespace

from xcore.configurations.loader import ConfigLoader
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.runtime.supervisor import PluginSupervisor
from xcore.kernel.tenancy.services import _current_tenant_id
from xcore.services.container import ServiceContainer

_YAML = """
app:
  name: t
  secret_key: test-secret-key-for-testing-min32chars
plugins:
  directory: {plugins}
  strict_trusted: false
  interval: 0
tenancy:
  enabled: true
  enforce_ipc: true
"""


def _add(sup, name, handler):
    sup._loader._handlers[name] = handler
    sup._permissions.grant_all(name)


class _Handler:
    def __init__(self, allowed, seen=None):
        self.manifest = SimpleNamespace(allowed_callers=allowed)
        self._seen = seen

    async def call(self, action, payload):
        if self._seen is not None:
            self._seen.append(_current_tenant_id.get())
        return {"status": "ok"}


async def _boot(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    cfg_file = tmp_path / "xcore.yaml"
    cfg_file.write_text(_YAML.format(plugins=plugins))
    cfg = ConfigLoader.load(cfg_file)
    ctx = KernelContext(
        config=cfg.plugins,
        services=ServiceContainer(cfg.services),
        events=EventBus(),
    )
    sup = PluginSupervisor(ctx)
    await sup.boot()
    return sup


async def test_config_racine_tenancy_atteint_les_plugins(tmp_path):
    sup = await _boot(tmp_path)
    t = sup._ctx.config.tenancy
    assert t.enabled is True and t.enforce_ipc is True


async def test_ipc_denied_si_caller_non_autorise(tmp_path):
    sup = await _boot(tmp_path)
    _add(sup, "target", _Handler(["x"]))
    denied = await sup.call("target", "ping", {}, caller="intruder")
    assert denied["status"] == "error" and denied["code"] == "ipc_denied"
    ok = await sup.call("target", "ping", {}, caller="x")
    assert ok["status"] == "ok"


async def test_deny_by_default_sans_allowed_callers(tmp_path):
    """Changement voulu : enforce_ipc + allowed_callers vide => refus."""
    sup = await _boot(tmp_path)
    _add(sup, "legacy", _Handler([]))
    res = await sup.call("legacy", "ping", {}, caller="any")
    assert res["code"] == "ipc_denied"


async def test_tenant_propage_quand_tenancy_activee(tmp_path):
    seen: list = []
    sup = await _boot(tmp_path)
    _add(sup, "t", _Handler(["*"], seen))
    await sup.call("t", "ping", {}, caller="a", tenant_id="acme")
    assert seen == ["acme"]


def test_warning_liste_les_plugins_sans_allowed_callers(monkeypatch):
    from xcore.kernel.runtime import supervisor as sup_mod

    class _Loader:
        _m = {"open": ["*"], "closed": [], "none": None}

        def get_manifest(self, n):
            return SimpleNamespace(allowed_callers=self._m[n])

    class _Log:
        def __init__(self):
            self.calls = []

        def warning(self, msg, **kw):
            self.calls.append((msg, kw))

    log = _Log()
    monkeypatch.setattr(sup_mod, "logger", log)
    sup = PluginSupervisor.__new__(PluginSupervisor)
    sup._loader = _Loader()
    sup._warn_plugins_without_allowed_callers(["open", "closed", "none"])
    assert log.calls[0][1] == {"plugins": ["closed", "none"]}
    log.calls.clear()
    sup._warn_plugins_without_allowed_callers(["open"])
    assert log.calls == []


def test_xcoreconfig_construite_a_la_main_partage_la_tenancy_racine():
    from xcore.configurations.sections import TenancyConfig, XcoreConfig

    cfg = XcoreConfig(tenancy=TenancyConfig(enabled=True, enforce_ipc=True))
    assert cfg.plugins.tenancy is cfg.tenancy
    assert cfg.plugins.tenancy.enabled is True
