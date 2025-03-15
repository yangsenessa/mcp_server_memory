import anyio
import click
import httpx
import mcp.types as types
from mcp.server.lowlevel import Server


async def fetch_website(
    url: str,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    headers = {
        "User-Agent": "MCP Test Server (github.com/modelcontextprotocol/python-sdk)"
    }
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        return [types.TextContent(type="text", text=response.text)]


@click.command()
@click.option("--port", default=8000, help="Port to listen on for SSE")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
def main(port: int, transport: str) -> int:
    app = Server("mcp-website-fetcher")

    @app.call_tool()
    async def fetch_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        if name != "fetch":
            raise ValueError(f"Unknown tool: {name}")
        if "url" not in arguments:
            raise ValueError("Missing required argument 'url'")
        return await fetch_website(arguments["url"])

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="fetch",
                description="Fetches a website and returns its content",
                inputSchema={
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to fetch",
                        }
                    },
                },
            )
        ]

    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")
        
        print("服务器已启动（SSE模式）")
        print("使用以下命令进行测试：")
        print(f"""
curl示例:
1. 获取可用工具列表:
   curl -N http://localhost:{port}/messages/ -H 'Request-Type: list_tools'

2. 获取网页内容:
   curl -N http://localhost:{port}/messages/ -H 'Request-Type: call_tool' \\
   -H 'Content-Type: application/json' \\
   -d '{{"name": "fetch", "arguments": {{"url": "https://example.com"}}}}'

JavaScript fetch示例:
1. 获取可用工具列表:
   fetch('http://localhost:{port}/messages/', {{
       method: 'GET',
       headers: {{
           'Request-Type': 'list_tools'
       }}
   }}).then(response => response.json())
     .then(data => console.log(data));

2. 获取网页内容:
   fetch('http://localhost:{port}/messages/', {{
       method: 'POST',
       headers: {{
           'Request-Type': 'call_tool',
           'Content-Type': 'application/json'
       }},
       body: JSON.stringify({{
           name: 'fetch',
           arguments: {{
               url: 'https://example.com'
           }}
       }})
   }}).then(response => response.json())
     .then(data => console.log(data));
        """)

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        import uvicorn

        uvicorn.run(starlette_app, host="0.0.0.0", port=port)
    else:
        from mcp.server.stdio import stdio_server
        
        print("服务器已启动（stdio模式）")
        print("等待输入中... 按 Ctrl+C 退出")
        
        async def arun():
            async with stdio_server() as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )

        anyio.run(arun)

    return 0

if __name__ == "__main__":
    main()