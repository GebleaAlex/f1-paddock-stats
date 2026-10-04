import asyncio

import pytest

from paddock import config

pytestmark = pytest.mark.skipif(not config.current_db_path().exists(), reason="run `paddock update` first")
mcp = pytest.importorskip("mcp")


def test_mcp_tools_answer():
    from paddock.mcp_server import server

    async def go():
        tools = {t.name for t in await server.list_tools()}
        assert {
            "search",
            "get_race",
            "title_odds",
            "explore_results",
            "compare_laps",
            "simulate_strategy",
            "car_ratings",
            "circuit_conditions",
        } <= tools
        assert "MP4/4" in str(await server.call_tool("car_ratings", {"year": 1988}))
        result = await server.call_tool("search", {"query": "senna"})
        return str(result)

    assert "ayrton-senna" in asyncio.run(go())
