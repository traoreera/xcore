from dataclasses import dataclass, field

from xcore.sdk.plugin_base import PluginDependency

FORBIDDEN_BUILTINS = {
    "eval",
    "exec",
    "compile",
    "hasattr",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "breakpoint",
    "__import__",
    "pickle",
    "shelve",
    "marshal",
    "dir",
    "vars",
    "input",
    "help",
}

FORBIDDEN_ATTRIBUTES = {
    "__class__",
    "__globals__",
    "__subclasses__",
    "__code__",
    "__mro__",
    "__builtins__",
    "__dict__",
    "__base__",
    "__bases__",
    "__getattribute__",
}

DEFAULT_FORBIDDEN = {
    "posix",
    "pwd",
    "grp",
    "resource",
    "os",
    "sys",
    "subprocess",
    "shutil",
    "signal",
    "ctypes",
    "cffi",
    "mmap",
    "socket",
    "ssl",
    "http",
    "urllib",
    "httpx",
    "requests",
    "aiohttp",
    "websockets",
    "importlib",
    "imp",
    "builtins",
    "inspect",
    "gc",
    "tracemalloc",
    "dis",
    "tempfile",
    "glob",
    "multiprocessing",
    "threading",
    "concurrent",
    "pty",
    "termios",
    "tty",
    "fcntl",
} | FORBIDDEN_BUILTINS

DEFAULT_ALLOWED = {
    "json",
    "re",
    "math",
    "random",
    "datetime",
    "time",
    "pathlib",
    "typing",
    "dataclasses",
    "enum",
    "functools",
    "itertools",
    "collections",
    "string",
    "hashlib",
    "base64",
    "asyncio",
    "logging",
    "__future__",
    "xcore",
    "xcore.*",
    "xcore.sdk.*",
}


@dataclass
class ScanResult:
    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scanned: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def __str__(self) -> str:
        lines = [f"Scan {'✅' if self.passed else '❌'}"]
        lines += [f"  ❌ {e}" for e in self.errors]
        lines += [f"  ⚠️  {w}" for w in self.warnings]
        return "\n".join(lines)


class _SimpleManifest:
    """Manifeste minimal quand le SDK complet n'est pas disponible."""

    def __init__(self, raw, mode, env, requires: list, plugin_dir):
        self.name = str(raw["name"])
        self.version = str(raw["version"])
        self.execution_mode = mode
        self.author = raw.get("author", "unknown")
        self.description = raw.get("description", "")
        self.framework_version = raw.get("framework_version", ">=2.0")
        self.entry_point = raw.get("entry_point", "src/main.py")
        self.allowed_imports = raw.get("allowed_imports", [])
        self.env = env
        # Convertit les dépendances en PluginDependency si ce sont des strings
        self.requires = [
            dep if isinstance(dep, PluginDependency) else PluginDependency.from_raw(dep)
            for dep in requires
        ]
        self.plugin_dir = plugin_dir
        self.extra = {}

        # Defaults resources/runtime
        from types import SimpleNamespace

        rl = SimpleNamespace(calls=100, period_seconds=60)
        self.resources = SimpleNamespace(
            timeout_seconds=10, max_memory_mb=128, max_disk_mb=50, rate_limit=rl
        )
        hc = SimpleNamespace(enabled=True, interval_seconds=30, timeout_seconds=3)
        retry = SimpleNamespace(max_attempts=1, backoff_seconds=0.0)
        self.runtime = SimpleNamespace(health_check=hc, retry=retry)
        fs = SimpleNamespace(allowed_paths=["data/"], denied_paths=["src/"])
        self.filesystem = fs
