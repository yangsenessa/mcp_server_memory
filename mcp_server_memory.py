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


if sys.platform == "darwin":  # Mac OS
    print("\033[1;32mStarting MCP Memory Server\033[0m")
    print("\033[1;34mby Mixlab - GitHub: https://github.com/shadowcz007/memory_mcp\033[0m")
    print("\033[1;36mTutorial: https://mp.weixin.qq.com/s/kiDlpgWqmo0eDYNd7Extmg\033[0m")
else:  # Windows 和其他平台
    print("\033[1;32mStarting MCP Memory Server\033[0m")
    print("\033[1;34mby Mixlab \033]8;;https://github.com/shadowcz007/memory_mcp\033\\GitHub\033]8;;\033\\\033[0m")
    print("\033[1;36mTutorial: \033]8;;https://mp.weixin.qq.com/s/kiDlpgWqmo0eDYNd7Extmg\033\\点击查看教程\033]8;;\033\\\033[0m")
print()
print()

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
    config = uvicorn.Config(starlette_app, host="localhost", port=port)
    server = uvicorn.Server(config)
    await server.serve()

def get_user_input(prompt: str, default: str) -> str:
    """获取用户输入，如果用户直接回车则使用默认值"""
    try:
        user_input = input(f"{prompt} (默认: {default}): ").strip()
        # 移除可能存在的 BOM
        if user_input.startswith('\ufeff'):
            user_input = user_input[1:]
        return user_input if user_input else default
    except Exception as e:
        print(f"输入处理错误: {e}")
        return default

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
    
    # 加载上次的配置
    last_config = load_config()
    port = None
    memory_path = None
    
    # 1. 首先检查是否有 stdin 输入
    try:
        # 检查stdin是否有数据可读
        if not sys.stdin.isatty():  # 如果stdin不是终端，说明可能有管道输入
            json_str = sys.stdin.read().strip()
            if json_str:  # 确保输入不为空
                if json_str.startswith('\ufeff'):
                    json_str = json_str[1:]
                stdin_config = json.loads(json_str)
                
                port = stdin_config.get('port')
                memory_path = stdin_config.get('memory_path')
                
                # 如果成功从stdin读取配置，直接使用这些值
                if port is not None and memory_path is not None:
                    print(f"从stdin读取配置: 端口={port}, 内存路径={memory_path}")
    except Exception as e:
        print(f"处理 stdin 输入时出错: {e}")
        # 继续执行，尝试其他配置方式
    
    # 2. 如果没有 stdin 输入，检查命令行参数
    if port is None:
        port = args.port
    if memory_path is None:
        memory_path = args.memory_path
        
    # 3. 如果仍然没有配置，使用用户交互输入
    if port is None:
        default_port = str(last_config.get('port', 8080))
        port = int(get_user_input("请输入服务器端口号", default_port))
        
    if memory_path is None:
        if getattr(sys, 'frozen', False):
            default_memory_path = Path(sys.executable).parent / "memory.json"
        else:
            default_memory_path = Path(__file__).parent / "memory.json"
            
        saved_memory_path = last_config.get('memory_path')
        default_path = saved_memory_path if saved_memory_path else str(default_memory_path)
        memory_path = get_user_input("请输入内存文件路径", default_path)

    # 处理内存文件路径
    memory_path = Path(memory_path)
    if not memory_path.is_absolute():
        if getattr(sys, 'frozen', False):
            memory_path = Path(sys.executable).parent / memory_path
        else:
            memory_path = Path(__file__).parent / memory_path
    
    print(f"Memory file will be stored at: {memory_path.resolve()}")
    print(f"Server will run on port: {port}")
    
    # 保存配置并启动服务器
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    save_config(port, str(memory_path))
    asyncio.run(main(str(memory_path), port))
