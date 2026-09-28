"""
conftest.py – Fixtures globales pour la suite de tests xcore
=============================================================
Utilisées automatiquement par pytest dans tous les fichiers de test.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Forcer l'environnement de test ────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-xcore-ci-only")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("TESTING", "true")


# ── App FastAPI minimale pour les tests ───────────────────────────────────────
@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Application FastAPI de test — importe main seulement si disponible."""
    try:
        from main import app as _app

        return _app
    except ImportError:
        # Fallback : app minimale si main.py absent
        _app = FastAPI(title="xcore-test")
        return _app


@pytest.fixture(scope="session")
def client(app: FastAPI) -> Generator:
    """Client HTTP pour tester les routes."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Base de données de test ───────────────────────────────────────────────────
@pytest.fixture(scope="session")
def db_engine():
    """Moteur SQLAlchemy en mémoire pour les tests."""
    try:
        from extensions.services.database import Base
        from sqlalchemy import create_engine

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
    except ImportError:
        yield None


@pytest.fixture
def db_session(db_engine):
    """Session SQLAlchemy isolée par test — rollback automatique."""
    if db_engine is None:
        yield None
        return

    from sqlalchemy.orm import sessionmaker

    TestingSession = sessionmaker(bind=db_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ── Dossier temporaire pour les plugins ───────────────────────────────────────
@pytest.fixture
def plugins_dir() -> Generator:
    """Crée un dossier temporaire pour simuler plugins/ lors des tests."""
    tmp = tempfile.mkdtemp(prefix="xcore_test_plugins_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def fake_plugin_dir(plugins_dir: Path) -> Path:
    """
    Crée un plugin factice valide dans le dossier temporaire.
    Structure v2 respectant le contrat xcore.
    """
    plugin = plugins_dir / "test_plugin"
    plugin.mkdir()

    src = plugin / "src"
    src.mkdir()

    (src / "__init__.py").write_text("")

    (src / "main.py").write_text(
        "from fastapi import APIRouter, Request\n"
        "from xcore import TrustedBase\n\n"
        "router = APIRouter()\n\n"
        "class Plugin(TrustedBase):\n"
        "    def __init__(self, ctx, caller):\n"
        "        super().__init__(ctx, caller)\n\n"
        "    @router.get('/')\n"
        "    async def index(self, request: Request):\n"
        "        return {'status': 'ok', 'plugin': 'test'}\n"
    )

    (plugin / "plugin.yaml").write_text(
        "name: test_plugin\n"
        "version: '1.0.0'\n"
        "author: test\n"
        "execution_mode: trusted\n"
        "entry_point: src/main.py\n"
    )

    return plugin


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Fixture utilitaire pour un dossier temporaire propre."""
    # Préfixe distinctif : permet à _cleanup_stray_tmp_dirs (ci-dessous) de
    # cibler précisément ces dossiers sans risquer de toucher aux tmp d'un
    # autre processus si ce yield+rmtree n'a pas pu s'exécuter (crash dur).
    tmp = tempfile.mkdtemp(prefix="xcore_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


def sweep_stray_tmp_dirs() -> None:
    """
    Balaie tout ce qui porte le préfixe `xcore_test_` restant dans le dossier
    temp système — jamais plus large, pour ne pas toucher aux fichiers
    temporaires d'un autre processus. Fonction plain (pas une fixture) pour
    rester testable directement.
    """
    tmp_root = Path(tempfile.gettempdir())
    for leftover in tmp_root.glob("xcore_test_*"):
        shutil.rmtree(leftover, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_stray_tmp_dirs() -> Generator[None, None, None]:
    """
    Filet de sécurité en fin de session : `plugins_dir`/`temp_dir` nettoient
    déjà systématiquement leur propre dossier via yield+rmtree, mais ce
    teardown ne s'exécute pas si un test crashe durement (SIGKILL) avant
    d'y arriver.
    """
    yield
    sweep_stray_tmp_dirs()


@pytest.fixture
def invalid_plugin_dir(plugins_dir: Path) -> Path:
    """Plugin invalide — manque PLUGIN_INFO."""
    plugin = plugins_dir / "bad_plugin"
    plugin.mkdir()
    (plugin / "__init__.py").write_text("")
    (plugin / "run.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "# PLUGIN_INFO manquant volontairement\n"
        "class Plugin:\n"
        "    def __init__(self): super().__init__()\n"
    )
    return plugin


# ── Tokens JWT de test ────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def user_token(client: TestClient) -> str:
    """Retourne un token JWT utilisateur valide."""
    try:
        resp = client.post(
            "/auth/login",
            json={
                "email": "test@xcore.dev",
                "password": "testpassword123",
            },
        )
        if resp.status_code == 200:
            return resp.json().get("access_token", "")
    except Exception:
        pass
    # Fallback : génération directe du token
    try:
        from extensions.services.security import create_token

        return create_token({"user_id": 1, "email": "test@xcore.dev", "role": "user"})
    except ImportError:
        return "fake-token-for-tests"


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    """Retourne un token JWT admin valide."""
    try:
        resp = client.post(
            "/auth/login",
            json={
                "email": "admin@xcore.dev",
                "password": "adminpassword123",
            },
        )
        if resp.status_code == 200:
            return resp.json().get("access_token", "")
    except Exception:
        pass
    try:
        from extensions.services.security import create_token

        return create_token({"user_id": 0, "email": "admin@xcore.dev", "role": "admin"})
    except ImportError:
        return "fake-admin-token-for-tests"


@pytest.fixture
def auth_headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


# ── Mock Redis ────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_redis():
    """Redis mocké — évite une vraie connexion en CI."""
    store = {}

    redis_mock = MagicMock()
    redis_mock.get.side_effect = lambda k: store.get(k)
    redis_mock.set.side_effect = lambda k, v, ex=None: store.update({k: v})
    redis_mock.delete.side_effect = lambda k: store.pop(k, None)
    redis_mock.exists.side_effect = lambda k: k in store
    redis_mock.ping.return_value = True

    with patch(
        "xcore.integration.services.cache.CacheService", return_value=redis_mock
    ):
        yield redis_mock


# ── Utilitaire : créer un utilisateur de test ─────────────────────────────────
@pytest.fixture
def test_user(db_session):
    """Crée un utilisateur de test en base."""
    try:
        from extensions.services.database import User  # adapter selon ton modèle
        from extensions.services.security import hash_password

        user = User(
            email="test@xcore.dev",
            hashed_password=hash_password("testpassword123"),
            role="user",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        yield user
        db_session.delete(user)
        db_session.commit()
    except (ImportError, Exception):
        yield MagicMock(
            id=1,
            email="test@xcore.dev",
            role="user",
            is_active=True,
        )
