import asyncio
from unittest.mock import AsyncMock, patch
from xcore.cli.marketplace_cmd import _mkt_list, _mkt_trending, _mkt_search

# Mock data
MOCK_PLUGINS = [
    {
        "name": "auth-plugin",
        "version": "1.2.3",
        "author": "Alice",
        "rating": 4.5,
        "description": "Authentification service for XCore",
        "downloads": 1500
    },
    {
        "name": "database-manager",
        "version": "0.9.0",
        "author": "Bob",
        "rating": 3.0,
        "description": "SQL and NoSQL management",
        "downloads": 800
    },
    {
        "name": "image-processor",
        "version": "2.1.0",
        "author": "Charlie",
        "rating": 5.0,
        "description": "Advanced image processing tools",
        "downloads": 3000
    }
]

async def run_verifications():
    class Args:
        query = "auth"
        config = None

    args = Args()

    with patch("xcore.cli.marketplace_cmd._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.list_plugins.return_value = MOCK_PLUGINS
        mock_client.trending.return_value = MOCK_PLUGINS
        mock_client.search.return_value = MOCK_PLUGINS
        mock_get_client.return_value = (mock_client, None)

        print("--- Testing _mkt_list ---")
        await _mkt_list(args)
        print("\n--- Testing _mkt_trending ---")
        await _mkt_trending(args)
        print("\n--- Testing _mkt_search ---")
        await _mkt_search(args)

if __name__ == "__main__":
    asyncio.run(run_verifications())
