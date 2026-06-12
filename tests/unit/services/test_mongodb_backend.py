
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from xcore.services.database.adapters.mongodb import MongoDBAdapter

class TestMongoDBAdapter:
    @pytest.fixture
    def cfg(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            url="mongodb://localhost:27017",
            database="testdb",
            max_connections=50
        )

    @pytest.fixture
    def adapter(self, cfg):
        return MongoDBAdapter("mongo", cfg)

    @pytest.mark.asyncio
    async def test_connect(self, adapter):
        mock_motor = MagicMock()
        mock_client_class = mock_motor.motor_asyncio.AsyncIOMotorClient
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.admin.command = AsyncMock(return_value={"ok": 1})

        with patch.dict("sys.modules", {"motor": mock_motor, "motor.motor_asyncio": mock_motor.motor_asyncio}):
            await adapter.connect()

            mock_client_class.assert_called_once_with(
                "mongodb://localhost:27017",
                maxPoolSize=50,
                serverSelectionTimeoutMS=5000
            )
            assert adapter._client == mock_client
            assert adapter._db == mock_client["testdb"]

    @pytest.mark.asyncio
    async def test_connect_import_error(self, adapter):
        with patch.dict("sys.modules", {"motor.motor_asyncio": None}):
            with pytest.raises(ImportError) as exc:
                await adapter.connect()
            assert "motor non installé" in str(exc.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        mock_client = MagicMock()
        adapter._client = mock_client

        await adapter.disconnect()

        mock_client.close.assert_called_once()
        assert adapter._client is None
        assert adapter._db is None

    def test_collection_access(self, adapter):
        mock_db = MagicMock()
        adapter._db = mock_db

        col = adapter.collection("users")
        assert col == mock_db["users"]

    def test_collection_not_initialized(self, adapter):
        with pytest.raises(RuntimeError) as exc:
            adapter.collection("users")
        assert "non initialisé" in str(exc.value)

    def test_database_access(self, adapter):
        mock_db = MagicMock()
        adapter._db = mock_db
        assert adapter.database() == mock_db

    def test_database_not_initialized(self, adapter):
        with pytest.raises(RuntimeError) as exc:
            adapter.database()
        assert "non initialisé" in str(exc.value)

    @pytest.mark.asyncio
    async def test_ping(self, adapter):
        mock_client = MagicMock()
        adapter._client = mock_client
        mock_client.admin.command = AsyncMock(return_value={"ok": 1.0})

        ok, msg = await adapter.ping()
        assert ok is True
        assert msg == "ok"

    @pytest.mark.asyncio
    async def test_ping_failure(self, adapter):
        mock_client = MagicMock()
        adapter._client = mock_client
        mock_client.admin.command = AsyncMock(side_effect=Exception("error"))

        ok, msg = await adapter.ping()
        assert ok is False
        assert msg == "error"
