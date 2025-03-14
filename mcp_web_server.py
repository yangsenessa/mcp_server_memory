import asyncio
import json
from contextlib import AsyncExitStack
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from threading import Thread
import os

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
                    print(f"获取工具列表失败: {str(e)}")  # 添加错误日志
                    import traceback
                    print(traceback.format_exc())  # 添加详细的错误堆栈
                    self._send_response(500, {
                        "success": False,
                        "error": str(e)
                    })

            # 使用 Future 来等待异步操作完成
            future = asyncio.run_coroutine_threadsafe(list_tools(), mcp_client._loop)
            try:
                future.result(timeout=10)  # 设置超时时间为10秒
            except Exception as e:
                print(f"执行异步操作失败: {str(e)}")
                self._send_response(500, {
                    "success": False,
                    "error": "执行异步操作失败"
                })
        else:
            self._send_response(404, {
                "success": False,
                "error": "未找到该端点"
            })

    async def handle_tool_call(self, tool_name: str, tool_args: dict):
        try:
            print(f"正在调用工具: {tool_name}，参数: {tool_args}")
            result = await mcp_client.session.call_tool(tool_name, tool_args)
            print(f"工具调用结果: {result}")
            
            # 将 TextContent 对象转换为可序列化的格式
            content_list = []
            for content in result.content:
                content_dict = {
                    "type": content.type,
                    "text": content.text,
                    "annotations": content.annotations
                }
                content_list.append(content_dict)
            
            return {
                "success": not result.isError,
                "data": content_list,
                "meta": result.meta
            }
        except Exception as e:
            print(f"工具调用失败: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return {"success": False, "error": str(e)}

    def do_POST(self):
        try:
            if self.path == "/tool/call":
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                request_data = json.loads(post_data.decode('utf-8'))
                
                print(f"收到POST请求数据: {request_data}")  # 添加日志
                
                tool_name = request_data.get('tool_name')
                tool_args = request_data.get('tool_args', {})
                
                if not tool_name:
                    self.send_error(400, "Missing tool_name")
                    return
                
                result = asyncio.run_coroutine_threadsafe(
                    self.handle_tool_call(tool_name, tool_args),
                    mcp_client._loop
                ).result()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_error(404)
        except Exception as e:
            print(f"请求处理失败: {str(e)}")  # 添加错误日志
            import traceback
            print(traceback.format_exc())  # 添加详细的错误堆栈
            self.send_error(500)

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
    print(f"正在连接到MCP服务器脚本: {server_script_path}")  # 添加日志
    try:
        await mcp_client.connect_to_server(server_script_path)
    except Exception as e:
        print(f"连接MCP服务器失败: {str(e)}")  # 添加错误日志
        raise

def run_server(host: str = "localhost", port: int = 8000, server_script_path: str = "path/to/your/server.py"):
    print(f"正在初始化MCP Web服务器...")  # 添加日志
    
    # 验证服务器脚本路径
    if not os.path.exists(server_script_path):  # 需要在文件顶部添加 import os
        print(f"错误: 找不到服务器脚本: {server_script_path}")
        return
        
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mcp_client._loop = loop
    
    try:
        # 初始化MCP客户端
        print("正在初始化MCP客户端...")  # 添加日志
        loop.run_until_complete(init_mcp_client(server_script_path))
        
        # 启动HTTP服务器
        server = HTTPServer((host, port), MCPRequestHandler)
        print(f"HTTP服务器已启动在 http://{host}:{port}")  # 修改日志信息
        print("按Ctrl+C停止服务器")  # 添加提示信息
        
        # 在单独的线程中运行事件循环
        def run_loop():
            loop.run_forever()
        
        loop_thread = Thread(target=run_loop, daemon=True)
        loop_thread.start()
        
        # 在主线程中运行HTTP服务器
        server.serve_forever()
    except Exception as e:
        print(f"服务器启动失败: {str(e)}")  # 添加错误日志
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
    finally:
        server.server_close()
        loop.run_until_complete(mcp_client.cleanup())
        loop.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python mcp_web_server.py <MCP服务器脚本路径>")
        print("示例: python mcp_web_server.py ./mcp_server.py")
        sys.exit(1)
    
    run_server(server_script_path=sys.argv[1])