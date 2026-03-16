
import asyncio
from unittest.mock import MagicMock, AsyncMock
from rich.console import Console
from xcore.cli.marketplace_cmd import _mkt_list, _mkt_trending, _mkt_search, _mkt_show, _mkt_rate, _stars

async def verify_ui():
    console = Console()

    # Mock data
    mock_plugins = [
        {"name": "auth-plugin", "version": "1.2.0", "author": "Alice", "rating": 4.5, "description": "Authentication module", "downloads": 1500},
        {"name": "storage-s3", "version": "0.9.0", "author": "Bob", "rating": None, "description": "S3 Storage adapter", "downloads": 800},
        {"name": "logger-pro", "version": "2.1.1", "author": "Charlie", "rating": "invalid", "description": "Advanced logging", "downloads": 3200},
    ]

    # Mock Client
    mock_client = MagicMock()
    mock_client.list_plugins = AsyncMock(return_value=mock_plugins)
    mock_client.trending = AsyncMock(return_value=mock_plugins)
    mock_client.search = AsyncMock(return_value=mock_plugins)
    mock_client.get_plugin = AsyncMock(return_value=mock_plugins[0])
    mock_client.get_versions = AsyncMock(return_value=[{"version": "1.2.0", "latest": True, "released_at": "2023-10-01"}])
    mock_client.rate_plugin = AsyncMock(return_value={"new_rating": 4.6, "rating_count": 11})

    # Mock _get_client helper
    import xcore.cli.marketplace_cmd
    xcore.cli.marketplace_cmd._get_client = MagicMock(return_value=(mock_client, MagicMock()))

    console.rule("[bold]Testing _mkt_list (with rating edge cases)")
    await _mkt_list(MagicMock())

    console.rule("[bold]Testing _mkt_trending")
    await _mkt_trending(MagicMock())

    console.rule("[bold]Testing _mkt_search")
    args_search = MagicMock()
    args_search.query = "auth"
    await _mkt_search(args_search)

    console.rule("[bold]Testing _mkt_show")
    args_show = MagicMock()
    args_show.name = "auth-plugin"
    await _mkt_show(args_show)

    console.rule("[bold]Testing _mkt_rate")
    args_rate = MagicMock()
    args_rate.name = "auth-plugin"
    args_rate.score = 5
    await _mkt_rate(args_rate)

    console.rule("[bold]Testing error handling (should not crash)")
    mock_client.list_plugins = AsyncMock(side_effect=Exception("API is down"))
    try:
        # This will sys.exit(1), so we wrap it or mock sys.exit
        import sys
        original_exit = sys.exit
        sys.exit = MagicMock()
        await _mkt_list(MagicMock())
        sys.exit = original_exit
        console.print("[green]Error handled without crash[/]")
    except Exception as e:
        console.print(f"[red]Crashed with: {e}[/]")

if __name__ == "__main__":
    asyncio.run(verify_ui())
