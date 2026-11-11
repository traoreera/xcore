"""`import xcore` does not pay for celery or SQLAlchemy (issues #305 point 2, #306).

`xcore/sdk/__init__.py` imported `..services.xworker` (celery) eagerly, and the external `xcoresdk`
package (which drags SQLAlchemy through its auth module). Both were paid by every application that
does `import xcore` — and by EVERY sandbox worker, at every recycle, even with no worker service and
no database configured. Measured: `import xcore` 594 ms -> 294 ms once both are lazy.

What these tests defend, each in a FRESH interpreter (`sys.modules` is global, so an earlier test
importing celery would hide the regression):
- after `import xcore`, neither celery nor sqlalchemy is in `sys.modules`;
- the names are still reachable, and `from xcore.sdk import *` still exposes them;
- the first access does the import, so nothing is silently broken for the plugins that use them.
"""

import subprocess
import sys

import pytest


def _run(code: str) -> str:
    """Run `code` in a fresh interpreter and return its stdout (fails the test on a non-zero exit)."""
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


class TestNothingHeavyAtImportTime:
    @pytest.mark.parametrize("heavy", ["celery", "sqlalchemy"])
    def test_import_xcore_does_not_import_it(self, heavy):
        loaded = _run(f"import sys, xcore; print({heavy!r} in sys.modules)")
        assert loaded == "False"

    @pytest.mark.parametrize("heavy", ["celery", "sqlalchemy"])
    def test_importing_the_sdk_itself_does_not_import_it_either(self, heavy):
        loaded = _run(f"import sys, xcore.sdk; print({heavy!r} in sys.modules)")
        assert loaded == "False"


class TestTheNamesStillWork:
    def test_the_worker_service_resolves_and_only_then_pulls_celery(self):
        out = _run(
            "import sys, xcore.sdk as s\n"
            "before = 'celery' in sys.modules\n"
            "name = s.WorkerService.__name__\n"
            "print(before, name, 'celery' in sys.modules)"
        )
        assert out == "False WorkerService True"

    def test_task_and_task_registry_resolve(self):
        out = _run(
            "from xcore.sdk import task, task_registry\n"
            "print(callable(task), task_registry is not None)"
        )
        assert out == "True True"

    def test_a_star_import_still_exposes_the_lazy_names(self):
        """`__all__` must not shrink: a plugin doing `from xcore.sdk import *` kept working."""
        out = _run(
            "import xcore.sdk as s\n"
            "names = set(s.__all__)\n"
            "print(all(n in names for n in ('WorkerService', 'task', 'task_registry')))"
        )
        assert out == "True"

    def test_a_name_that_does_not_exist_still_raises_attribute_error(self):
        out = _run(
            "import xcore.sdk as s\n"
            "try:\n"
            "    s.PasDuTout\n"
            "except AttributeError as e:\n"
            "    print('AttributeError', 'PasDuTout' in str(e))"
        )
        assert out == "AttributeError True"
