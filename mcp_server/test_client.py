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
SERVER = REPO / "mcp_server" / "aviation_ontology_server.py"


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("=== 公開ツール ===")
            for t in tools.tools:
                print(f"  - {t.name}: {(t.description or '').splitlines()[0]}")

            print("\n=== disrupted_flights ===")
            res = await session.call_tool("disrupted_flights", {})
            print(res.content[0].text)

            print("\n=== sparql_query (国内線の一覧) ===")
            res = await session.call_tool("sparql_query", {"query": """
                SELECT ?label WHERE {
                  ?f a avi:DomesticFlight ; rdfs:label ?label .
                  FILTER(LANG(?label) = "ja")
                } ORDER BY ?label
            """})
            print(res.content[0].text)

            print("\n=== affected_passengers ===")
            res = await session.call_tool("affected_passengers", {})
            print(res.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
