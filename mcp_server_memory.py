import os
import sys
import json
from pathlib import Path
from dataclasses import dataclass

from mcp.server import Server 
from mcp.server.sse import SseServerTransport
import mcp.types as types
from starlette.applications import Starlette
from starlette.routing import Mount, Route 


print("Starting MCP Memory Server")

# 定义数据结构
@dataclass
class Entity:
    name: str
    entityType: str
    observations: list

@dataclass
class Relation:
    from_: str  # 使用 from_ 避免与 Python 关键字冲突
    to: str
    relationType: str

@dataclass
class KnowledgeGraph:
    entities: list
    relations: list

class KnowledgeGraphManager:
    def __init__(self, memory_path: str):
        self.memory_path = Path(memory_path).expanduser()
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

    async def load_graph(self) -> KnowledgeGraph:
        try:
            if not self.memory_path.exists():
                return KnowledgeGraph(entities=[], relations=[])
                
            data = await self._read_file()
            graph = KnowledgeGraph(entities=[], relations=[])
            
            for line in data.split("\n"):
                if not line.strip():
                    continue
                    
                item = json.loads(line)
                if item["type"] == "entity":
                    graph.entities.append(Entity(
                        name=item["name"],
                        entityType=item["entityType"],
                        observations=item["observations"]
                    ))
                elif item["type"] == "relation":
                    graph.relations.append(Relation(
                        from_=item["from"],
                        to=item["to"],
                        relationType=item["relationType"]
                    ))
            
            return graph
            
        except Exception as e:
            print(f"Error loading graph: {e}")
            return KnowledgeGraph(entities=[], relations=[])

    async def save_graph(self, graph: KnowledgeGraph):
        try:
            lines = []
            for entity in graph.entities:
                lines.append(json.dumps({
                    "type": "entity",
                    "name": entity.name,
                    "entityType": entity.entityType,
                    "observations": entity.observations
                }, ensure_ascii=False))
                
            for relation in graph.relations:
                lines.append(json.dumps({
                    "type": "relation", 
                    "from": relation.from_,
                    "to": relation.to,
                    "relationType": relation.relationType
                }, ensure_ascii=False))
                
            await self._write_file("\n".join(lines))
            
        except Exception as e:
            print(f"Error saving graph: {e}")
            raise

    async def _read_file(self) -> str:
        with open(self.memory_path, "r", encoding="utf-8") as f:
            return f.read()

    async def _write_file(self, content: str):
        with open(self.memory_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    async def create_entities(self, entities: list) -> list:
        graph = await self.load_graph()
        new_entities = [e for e in entities 
                       if not any(ex.name == e.name for ex in graph.entities)]
        graph.entities.extend(new_entities)
        await self.save_graph(graph)
        return new_entities

    async def create_relations(self, relations: list) -> list:
        graph = await self.load_graph()
        new_relations = [r for r in relations 
                        if not any(ex.from_ == r.from_ and 
                                 ex.to == r.to and 
                                 ex.relationType == r.relationType 
                                 for ex in graph.relations)]
        graph.relations.extend(new_relations)
        await self.save_graph(graph)
        return new_relations

    async def add_observations(self, observations: list) -> list:
        graph = await self.load_graph()
        results = []
        
        for obs in observations:
            entity = next((e for e in graph.entities if e.name == obs["entityName"]), None)
            if not entity:
                raise ValueError(f"Entity with name {obs['entityName']} not found")
                
            new_observations = [c for c in obs["contents"] 
                              if c not in entity.observations]
            entity.observations.extend(new_observations)
            
            results.append({
                "entityName": obs["entityName"],
                "addedObservations": new_observations
            })
            
        await self.save_graph(graph)
        return results

    async def delete_entities(self, entity_names: list) -> None:
        graph = await self.load_graph()
        graph.entities = [e for e in graph.entities 
                         if e.name not in entity_names]
        graph.relations = [r for r in graph.relations 
                         if r.from_ not in entity_names and 
                         r.to not in entity_names]
        await self.save_graph(graph)

    async def delete_observations(self, deletions: list) -> None:
        graph = await self.load_graph()
        
        for deletion in deletions:
            entity = next((e for e in graph.entities 
                          if e.name == deletion["entityName"]), None)
            if entity:
                entity.observations = [o for o in entity.observations 
                                     if o not in deletion["observations"]]
                
        await self.save_graph(graph)

    async def delete_relations(self, relations: list) -> None:
        graph = await self.load_graph()
        graph.relations = [r for r in graph.relations 
                         if not any(dr.from_ == r.from_ and 
                                  dr.to == r.to and 
                                  dr.relationType == r.relationType 
                                  for dr in relations)]
        await self.save_graph(graph)

    async def read_graph(self) -> KnowledgeGraph:
        return await self.load_graph()

    async def search_nodes(self, query: str) -> KnowledgeGraph:
        graph = await self.load_graph()
        
        # 过滤实体
        filtered_entities = [e for e in graph.entities 
                           if (query.lower() in e.name.lower() or
                               query.lower() in e.entityType.lower() or
                               any(query.lower() in o.lower() 
                                   for o in e.observations))]
        
        # 创建过滤后的实体名称集合
        filtered_entity_names = {e.name for e in filtered_entities}
        
        # 过滤关系
        filtered_relations = [r for r in graph.relations 
                            if r.from_ in filtered_entity_names and 
                            r.to in filtered_entity_names]
        
        return KnowledgeGraph(
            entities=filtered_entities,
            relations=filtered_relations
        )

    async def open_nodes(self, names: list) -> KnowledgeGraph:
        graph = await self.load_graph()
        
        # 过滤实体
        filtered_entities = [e for e in graph.entities 
                           if e.name in names]
        
        # 创建过滤后的实体名称集合
        filtered_entity_names = {e.name for e in filtered_entities}
        
        # 过滤关系
        filtered_relations = [r for r in graph.relations 
                            if r.from_ in filtered_entity_names and 
                            r.to in filtered_entity_names]
        
        return KnowledgeGraph(
            entities=filtered_entities,
            relations=filtered_relations
        )

async def main(memory_path: str, port: int = 8080):
    # 转换为绝对路径并显示
    absolute_memory_path = Path(memory_path).resolve()
    print(f"Starting Memory MCP Server with memory path: {absolute_memory_path} on port: {port}")
    
    graph_manager = KnowledgeGraphManager(str(absolute_memory_path))
    app = Server("memory-manager")

    @app.list_tools()
    async def handle_list_tools():
        return [
            types.Tool(
                name="create_entities",
                description="Create multiple new entities in the knowledge graph",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "entityType": {"type": "string"},
                                    "observations": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": ["name", "entityType", "observations"]
                            }
                        }
                    },
                    "required": ["entities"]
                }
            ),
            types.Tool(
                name="create_relations",
                description="Create multiple new relations between entities in the knowledge graph",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "relations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "from_": {"type": "string"},
                                    "to": {"type": "string"},
                                    "relationType": {"type": "string"}
                                },
                                "required": ["from_", "to", "relationType"]
                            }
                        }
                    },
                    "required": ["relations"]
                }
            ),
            types.Tool(
                name="add_observations",
                description="Add new observations to existing entities",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "observations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "entityName": {"type": "string"},
                                    "contents": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": ["entityName", "contents"]
                            }
                        }
                    },
                    "required": ["observations"]
                }
            ),
            types.Tool(
                name="delete_entities",
                description="Delete multiple entities and their relations",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entityNames": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["entityNames"]
                }
            ),
            types.Tool(
                name="delete_observations",
                description="Delete specific observations from entities",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "deletions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "entityName": {"type": "string"},
                                    "observations": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": ["entityName", "observations"]
                            }
                        }
                    },
                    "required": ["deletions"]
                }
            ),
            types.Tool(
                name="delete_relations",
                description="Delete multiple relations from the graph",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "relations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "from_": {"type": "string"},
                                    "to": {"type": "string"},
                                    "relationType": {"type": "string"}
                                },
                                "required": ["from_", "to", "relationType"]
                            }
                        }
                    },
                    "required": ["relations"]
                }
            ),
            types.Tool(
                name="read_graph",
                description="Read the entire knowledge graph",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            types.Tool(
                name="search_nodes",
                description="Search for nodes in the graph",
                inputSchema={
                    "type": "object", 
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            ),
            types.Tool(
                name="open_nodes",
                description="Open specific nodes by their names",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "names": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["names"]
                }
            )
        ]

    @app.call_tool()
    async def handle_call_tool(
        name: str, 
        arguments: dict | None
    ) -> list:
        try:
            if name == "read_graph":
                result = await graph_manager.read_graph()
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "entities": [vars(e) for e in result.entities],
                        "relations": [vars(r) for r in result.relations]
                    }, indent=2, ensure_ascii=False)
                )]
            
            if not arguments:
                raise ValueError("Missing arguments")
                
            if name == "create_entities":
                entities = [Entity(**e) for e in arguments["entities"]]
                result = await graph_manager.create_entities(entities)
                return [types.TextContent(
                    type="text",
                    text=json.dumps([vars(e) for e in result], indent=2, ensure_ascii=False)
                )]
                
            elif name == "create_relations":
                relations = [Relation(**r) for r in arguments["relations"]]
                result = await graph_manager.create_relations(relations)
                return [types.TextContent(
                    type="text",
                    text=json.dumps([vars(r) for r in result], indent=2, ensure_ascii=False)
                )]
                
            elif name == "add_observations":
                result = await graph_manager.add_observations(arguments["observations"])
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False)
                )]
                
            elif name == "delete_entities":
                await graph_manager.delete_entities(arguments["entityNames"])
                return [types.TextContent(
                    type="text",
                    text="Entities deleted successfully"
                )]
                
            elif name == "delete_observations":
                await graph_manager.delete_observations(arguments["deletions"])
                return [types.TextContent(
                    type="text",
                    text="Observations deleted successfully"
                )]
                
            elif name == "delete_relations":
                relations = [Relation(**r) for r in arguments["relations"]]
                await graph_manager.delete_relations(relations)
                return [types.TextContent(
                    type="text",
                    text="Relations deleted successfully"
                )]
                
            elif name == "search_nodes":
                result = await graph_manager.search_nodes(arguments["query"])
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "entities": [vars(e) for e in result.entities],
                        "relations": [vars(r) for r in result.relations]
                    }, indent=2, ensure_ascii=False)
                )]
                
            elif name == "open_nodes":
                result = await graph_manager.open_nodes(arguments["names"])
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "entities": [vars(e) for e in result.entities],
                        "relations": [vars(r) for r in result.relations]
                    }, indent=2, ensure_ascii=False)
                )]
            
            else:
                raise ValueError(f"Unknown tool: {name}")
            
        except Exception as e:
            print(f"Error in tool {name}: {str(e)}")
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    # 设置 SSE 服务器
    sse = SseServerTransport("/messages/")
    
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
            Route("/", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    # 启动服务器
    import uvicorn
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()

def get_user_input(prompt: str, default: str) -> str:
    """获取用户输入，如果用户直接回车则使用默认值"""
    user_input = input(f"{prompt} (默认: {default}): ").strip()
    return user_input if user_input else default

def get_config_path() -> Path:
    """获取配置文件路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的exe运行
        return Path(sys.executable).parent / "config.json"
    else:
        # 如果是源代码运行
        return Path(__file__).parent / "config.json"

def load_config() -> dict:
    """加载配置文件"""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(port: int, memory_path: str):
    """保存配置到文件"""
    config_path = get_config_path()
    config = {
        'port': port,
        'memory_path': str(memory_path)
    }
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置文件失败: {e}")

if __name__ == "__main__":
    import asyncio
    import argparse
    import sys
    import select

    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='MCP Memory Server')
    parser.add_argument('--port', type=int, help='服务器端口号')
    parser.add_argument('--memory-path', type=str, help='内存文件路径')
    
    args = parser.parse_args()
    
    # 修改检查 stdin 的方法
    if sys.platform == "win32":
        # Windows 系统使用 msvcrt 模块
        import msvcrt
        has_stdin_data = msvcrt.kbhit()
    else:
        # Unix 系统使用 select
        has_stdin_data = select.select([sys.stdin], [], [], 0.0)[0] != []

    # 加载上次的配置
    last_config = load_config()
    
    if has_stdin_data:
        # 从 stdin 读取 JSON 配置
        json_str = sys.stdin.read().strip()
        
        # 检查输入是否为空
        if not json_str:
            print("错误：输入为空，请提供有效的JSON配置")
            sys.exit(1)
            
        try:
            # 首先尝试直接解析
            stdin_config = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                # 尝试处理UTF-8 BOM
                stdin_config = json.loads(json_str.encode('utf-8').decode('utf-8-sig'))
            except:
                try:
                    # 尝试修复常见的JSON格式问题
                    json_str = json_str.replace("'", '"')  # 将单引号替换为双引号
                    stdin_config = json.loads(json_str)
                except json.JSONDecodeError:
                    print("错误：无法解析 stdin 的 JSON 数据")
                    sys.exit(1)
                    
        port = stdin_config.get('port', 8080)
        memory_path = stdin_config.get('memory_path')
        
        if not memory_path:
            print("错误：未提供 memory_path")
            sys.exit(1)
    else:
        # 获取端口号
        if args.port is not None:
            port = args.port
        else:
            default_port = str(last_config.get('port', 8080))
            port = int(get_user_input("请输入服务器端口号", default_port))
        
        # 获取内存文件路径
        if getattr(sys, 'frozen', False):
            default_memory_path = Path(sys.executable).parent / "memory.json"
        else:
            default_memory_path = Path(__file__).parent / "memory.json"

        if args.memory_path:
            memory_path = args.memory_path
        else:
            saved_memory_path = last_config.get('memory_path')
            default_path = saved_memory_path if saved_memory_path else str(default_memory_path)
            memory_path = get_user_input("请输入内存文件路径", default_path)
    
    # 确保内存文件路径是绝对路径
    memory_path = Path(memory_path)  # 首先转换为 Path 对象
    if not memory_path.is_absolute():
        memory_path = Path(__file__).parent / memory_path
    
    # 显示最终的内存文件路径
    print(f"Memory file will be stored at: {memory_path.resolve()}")
    print(f"Server will run on port: {port}")
    
    # 在 Windows 上运行时需要使用特定的事件循环策略
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 保存当前配置
    save_config(port, str(memory_path))
    
    asyncio.run(main(str(memory_path), port))  # 确保传入字符串形式的路径
