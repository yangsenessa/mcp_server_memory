import asyncio
import json
from contextlib import AsyncExitStack
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from threading import Thread

class MCPClient:
    """
    MCP客户端核心类
    
    负责管理与MCP服务器的连接、工具调用和资源管理。
    
    主要功能:
    1. 建立与MCP服务器的连接
    2. 管理可用工具列表
    3. 执行工具调用
    4. 管理资源生命周期
    """
    def __init__(self):
        # 初始化各种必要的组件
        self.session= None  # 存储与智能设备的连接状态
        self.exit_stack = AsyncExitStack()  # 管理各种设备的开关状态
        
    async def connect_to_server(self, server_script_path: str):
        """
        建立与MCP服务器的连接
        
        Args:
            server_script_path (str): 服务器脚本路径，支持.py或.js文件
            
        功能流程:
        1. 验证服务器脚本类型
        2. 初始化服务器连接
        3. 建立通信会话
        4. 获取可用工具列表
        
        Raises:
            ValueError: 当脚本类型不是.py或.js时抛出
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])
 
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

# 创建全局MCP客户端实例
mcp_client = MCPClient()

class MCPRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP请求处理器
    
    提供RESTful API接口，处理客户端请求并与MCP服务器交互。
    
    主要端点:
    - GET /tools: 获取可用工具列表
    - POST /tool/call: 调用指定工具
    - OPTIONS: 处理CORS预检请求
    """
    
    def _send_response(self, status_code: int, data: dict):
        """
        统一的HTTP响应处理方法
        
        Args:
            status_code (int): HTTP状态码
            data (dict): 响应数据
            
        功能:
        1. 设置响应状态码
        2. 配置CORS响应头
        3. 序列化并发送JSON响应
        """
        self.send_response(status_code)
        # 添加CORS相关的响应头
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # 允许所有域名访问
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        self.send_header('Access-Control-Max-Age', '3600')  # 预检请求的缓存时间
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _read_body(self):
        """读取请求体"""
        content_length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(content_length).decode('utf-8')

    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/tools':
            # 在事件循环中执行异步操作
            async def list_tools():
                try:
                    if not mcp_client.session:
                        return self._send_response(500, {
                            "success": False,
                            "error": "MCP客户端未连接"
                        })
                    
                    response = await mcp_client.session.list_tools()
                    tools = [{
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    } for tool in response.tools]
                    
                    self._send_response(200, {
                        "success": True,
                        "data": tools
                    })
                except Exception as e:
                    self._send_response(500, {
                        "success": False,
                        "error": str(e)
                    })

            asyncio.run_coroutine_threadsafe(list_tools(), mcp_client._loop)
        else:
            self._send_response(404, {
                "success": False,
                "error": "未找到该端点"
            })

    def do_POST(self):
        """处理POST请求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/tool/call':
            try:
                body = json.loads(self._read_body())
                tool_name = body.get('tool_name')
                tool_args = body.get('tool_args', {})
                
                if not tool_name:
                    self._send_response(400, {
                        "success": False,
                        "error": "缺少tool_name参数"
                    })
                    return

                # 在事件循环中执行异步操作
                async def call_tool():
                    try:
                        if not mcp_client.session:
                            return self._send_response(500, {
                                "success": False,
                                "error": "MCP客户端未连接"
                            })
                        
                        result = await mcp_client.session.call_tool(tool_name, tool_args)
                        self._send_response(200, {
                            "success": True,
                            "data": result.content
                        })
                    except Exception as e:
                        self._send_response(500, {
                            "success": False,
                            "error": str(e)
                        })

                asyncio.run_coroutine_threadsafe(call_tool(), mcp_client._loop)
            except json.JSONDecodeError:
                self._send_response(400, {
                    "success": False,
                    "error": "无效的JSON数据"
                })
        else:
            self._send_response(404, {
                "success": False,
                "error": "未找到该端点"
            })

    def do_OPTIONS(self):
        """处理OPTIONS预检请求"""
        self.send_response(200)
        # 添加CORS相关的响应头
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        self.send_header('Access-Control-Max-Age', '3600')
        self.end_headers()

async def init_mcp_client(server_script_path: str):
    """初始化MCP客户端"""
    await mcp_client.connect_to_server(server_script_path)
    
def run_server(host: str = "localhost", port: int = 8000, server_script_path: str = "path/to/your/server.py"):
    """
    启动MCP Web服务器
    
    Args:
        host (str): 服务器主机地址
        port (int): 服务器端口
        server_script_path (str): MCP服务器脚本路径
        
    功能流程:
    1. 初始化异步事件循环
    2. 建立MCP服务器连接
    3. 启动HTTP服务器
    4. 管理服务器生命周期
    
    注意:
        使用多线程处理异步事件循环和HTTP服务器
    """
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mcp_client._loop = loop
    
    # 初始化MCP客户端
    loop.run_until_complete(init_mcp_client(server_script_path))
    
    # 启动HTTP服务器
    server = HTTPServer((host, port), MCPRequestHandler)
    print(f"服务器启动在 http://{host}:{port}")
    
    try:
        # 在单独的线程中运行事件循环
        def run_loop():
            loop.run_forever()
        
        loop_thread = Thread(target=run_loop, daemon=True)
        loop_thread.start()
        
        # 在主线程中运行HTTP服务器
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
    finally:
        server.server_close()
        loop.run_until_complete(mcp_client.cleanup())
        loop.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_server_script>")
        sys.exit(1)
    
    run_server(server_script_path=sys.argv[1])