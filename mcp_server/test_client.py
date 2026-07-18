"""MCP サーバーの動作確認クライアント (Claude Code なしで検証できる)。

サーバーを stdio で起動し、ツール一覧の取得と代表的なツール呼び出しを行う。

    .venv/bin/python mcp_server/test_client.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "mcp_server" / "ontology_server.py"


async def call(session, name, args=None):
    print(f"\n=== {name}({args or ''}) ===")
    res = await session.call_tool(name, args or {})
    print(res.content[0].text)


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("=== 公開ツール ===")
            for t in tools.tools:
                print(f"  - {t.name}: {(t.description or '').splitlines()[0]}")

            await call(session, "disrupted_flights")
            await call(session, "alternate_airports", {"flight": "az987"})
            await call(session, "simulate_airport_disruption",
                       {"airport_codes": ["cts"]})
            await call(session, "disrupted_flights")  # シミュレーション反映を確認
            await call(session, "reload_graph")
            await call(session, "safe_dishes", {"avoid_allergens": ["小麦", "えび"]})
            await call(session, "sparql_query", {
                "graph": "cuisine",
                "query": """SELECT ?label WHERE {
                              ?d a cuisine:MeatDish ; rdfs:label ?label .
                              FILTER(LANG(?label) = "ja") }""",
            })


if __name__ == "__main__":
    asyncio.run(main())
