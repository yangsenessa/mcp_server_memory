from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # 可执行文件
    args=["mcp_server_memory.py", "--transport", "stdio"],  # 确保使用 stdio 传输模式
    env=None,  # 可选环境变量
)


# Optional: create a sampling callback
async def handle_sampling_message(
    message: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text="Hello, world! from model",
        ),
        model="gpt-3.5-turbo",
        stopReason="endTurn",
    )


async def run():
    try:
        print("正在启动 stdio 客户端...")
        async with stdio_client(server_params) as (read, write):
            print("stdio 客户端已启动，正在创建会话...")
            async with ClientSession(
                read, write, sampling_callback=handle_sampling_message
            ) as session:
                try:
                    # 初始化连接
                    print("正在初始化会话...")
                    await session.initialize()
                    print("会话初始化成功")
                    
                    # 列出可用工具
                    tools = await session.list_tools()
                    print(f"可用工具: {tools}")
                    
                    # 这里可以添加调用工具的代码
                    # 例如: result = await session.call_tool("read_graph", {})
                    # print(result)
                    
                except Exception as e:
                    print(f"会话操作错误: {e}")
    except Exception as e:
        print(f"连接错误: {e}")


if __name__ == "__main__":
    asyncio.run(run())