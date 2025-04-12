Analyze mcp_server_memmory.py, modify codes for the  response of 'help':
fill items of methods for following rules, including name,description,inputSchema:
the template of response body need to match json format strickly:
```
{
  "jsonrpc": "2.0",
  "result": {
    "type": "mcp",
    "description": "此服务是提供memory相关的mcp服务",
    "author": "shadow@Mixlab",
    "version": "1.2.0",
    "github": "https://github.com/shadowcz007/memory_mcp",
    "transport": [
      "stdio",
      "sse"
    ],
    "methods": [
      {
        "name": "help",
        "description": "显示此帮助信息。"
      },
      {
        "name": "start",
        "description": "启动服务器",
        "inputSchema": {
          "type": "object",
          "properties": {
            "transport": {
              "type": "string",
              "enum": [
                "stdio",
                "sse"
              ],
              "description": "传输类型",
              "default": "sse"
            },
            "port": {
              "type": "integer",
              "description": "服务器端口号 (仅在 transport=sse 时需要设置)",
              "default": 8080
            },
            "memory_path": {
              "type": "string",
              "description": "内存文件路径",
              "default": "./memory.json"
            }
          }
        }
      }
    ]
  },
  "id": 1743948342885
}
```
- add 'help' first as:
  {
        "name": "help",
        "description": "显示此帮助信息。"
  }

- For codes of '@app.list_tools()', analyse the detail of type.Tool and construct the dateitems detail of methods in response of 'help'

- For other codes like '@app.xxx()', analyze the related codes for 'methods' data item structure.