"""Verrou distribué du scheduler — testé contre un vrai redis-server."""

import asyncio
import shutil
import socket
import subprocess
import time

import pytest

import xcore.services.scheduler.service as svc_mod

redis_asyncio = pytest.importorskip("redis.asyncio")

pytestmark = pytest.mark.skipif(
    shutil.which("redis-server") is None, reason="redis-server indisponible"
)


@pytest.fixture(scope="module")
def redis_url(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [
            "redis-server",
            "--port", str(port),
            "--save", "",
            "--appendonly", "no",
            "--dir", str(tmp_path_factory.mktemp("redis")),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    yield f"redis://127.0.0.1:{port}/0"
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
async def client(redis_url, monkeypatch):
    c = redis_asyncio.from_url(redis_url, decode_responses=True)
    await c.flushall()
    monkeypatch.setattr(svc_mod, "_REDIS_LOCK_CLIENT", c)
    yield c
    await c.aclose()


@pytest.fixture(autouse=True)
def _registry():
    yield
    svc_mod._JOB_REGISTRY.pop("j", None)


KEY = "xcore:sched:lock:j"


async def test_lock_value_is_unique_token_and_released(client):
    seen = []

    async def job():
        seen.append(await client.get(KEY))

    svc_mod._JOB_REGISTRY["j"] = job
    await svc_mod._dispatch_job("j")
    assert seen[0] not in (None, "1")
    assert await client.get(KEY) is None


async def test_foreign_lock_is_not_deleted_after_expiry(client):
    async def job():
        # le TTL expire, un autre worker prend le verrou
        await client.set(KEY, "other-worker-token")

    svc_mod._JOB_REGISTRY["j"] = job
    await svc_mod._dispatch_job("j")
    assert await client.get(KEY) == "other-worker-token"


async def test_second_worker_skipped_while_running(client):
    started = asyncio.Event()
    release = asyncio.Event()
    runs = []

    async def job():
        runs.append(1)
        started.set()
        await release.wait()

    svc_mod._JOB_REGISTRY["j"] = job
    first = asyncio.create_task(svc_mod._dispatch_job("j"))
    await started.wait()
    await svc_mod._dispatch_job("j")  # autre worker : ignoré
    release.set()
    await first
    assert runs == [1]
    assert await client.get(KEY) is None


async def test_lock_renewed_for_jobs_longer_than_ttl(client, monkeypatch):
    monkeypatch.setattr(svc_mod, "_LOCK_TTL", 0.6)
    ttl_after = []

    async def job():
        await asyncio.sleep(1.5)  # > 2 x TTL
        ttl_after.append(await client.pttl(KEY))

    svc_mod._JOB_REGISTRY["j"] = job
    await svc_mod._dispatch_job("j")
    assert ttl_after[0] > 0  # le verrou existait encore (renouvelé)
    assert await client.get(KEY) is None


async def test_lock_released_when_job_raises(client):
    async def job():
        raise RuntimeError("boom")

    svc_mod._JOB_REGISTRY["j"] = job
    with pytest.raises(RuntimeError):
        await svc_mod._dispatch_job("j")
    assert await client.get(KEY) is None
