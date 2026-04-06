import pytest
from xcore import Xcore
from plugins.auth_plugin.src.services import AuthService, PermissionService
from plugins.auth_plugin.src.security import SecurityManager
from plugins.auth_plugin.src.models import User, UserStatus
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def security_manager():
    return SecurityManager(secret_key="test-secret")

@pytest.fixture
def mock_db():
    db = MagicMock()
    session = AsyncMock()
    db.session.return_value.__aenter__.return_value = session
    return db, session

@pytest.mark.asyncio
async def test_auth_service_authenticate_success(mock_db, security_manager):
    db_adapter, session = mock_db
    auth_service = AuthService(db_adapter, security_manager, {})

    password = "securepassword"
    hashed = security_manager.get_password_hash(password)
    user = User(id=1, email="test@example.com", username="testuser", password_hash=hashed, status=UserStatus.ACTIVE)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    session.execute.return_value = mock_result

    authenticated_user = await auth_service.authenticate_user("test@example.com", password)

    assert authenticated_user is not None
    assert authenticated_user.id == 1
    assert authenticated_user.username == "testuser"

@pytest.mark.asyncio
async def test_auth_service_authenticate_fail(mock_db, security_manager):
    db_adapter, session = mock_db
    auth_service = AuthService(db_adapter, security_manager, {})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    authenticated_user = await auth_service.authenticate_user("wrong@example.com", "password")

    assert authenticated_user is None
