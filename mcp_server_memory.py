import os
import sys
import json
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

from mcp.server import Server, NotificationOptions
from mcp.server.sse import SseServerTransport
import mcp.types as types
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from pydantic import AnyUrl

# 配置日志
logger = logging.getLogger('mcp_memory_server')
logger.info("Starting MCP Memory Server")

# 定义数据结构
@dataclass
class Entity:
    name: str
    entityType: str
    observations: List[str]

@dataclass
class Relation:
    from_: str  # 使用 from_ 避免与 Python 关键字冲突
    to: str
    relationType: str

@dataclass
class KnowledgeGraph:
    entities: List[Entity]
    relations: List[Relation]

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
            logger.error(f"Error loading graph: {e}")
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
                }))
                
            for relation in graph.relations:
                lines.append(json.dumps({
                    "type": "relation", 
                    "from": relation.from_,
                    "to": relation.to,
                    "relationType": relation.relationType
                }))
                
            await self._write_file("\n".join(lines))
            
        except Exception as e:
            logger.error(f"Error saving graph: {e}")
            raise

    async def _read_file(self) -> str:
        with open(self.memory_path, "r", encoding="utf-8") as f:
            return f.read()

    async def _write_file(self, content: str):
        with open(self.memory_path, "w", encoding="utf-8") as f:
            f.write(content)

    async def create_entities(self, entities: List[Entity]) -> List[Entity]:
        graph = await self.load_graph()
        new_entities = [e for e in entities 
                       if not any(ex.name == e.name for ex in graph.entities)]
        graph.entities.extend(new_entities)
        await self.save_graph(graph)
        return new_entities

    async def create_relations(self, relations: List[Relation]) -> List[Relation]:
        graph = await self.load_graph()
        new_relations = [r for r in relations 
                        if not any(ex.from_ == r.from_ and 
                                 ex.to == r.to and 
                                 ex.relationType == r.relationType 
                                 for ex in graph.relations)]
        graph.relations.extend(new_relations)
        await self.save_graph(graph)
        return new_relations

    async def add_observations(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    async def delete_entities(self, entity_names: List[str]) -> None:
        graph = await self.load_graph()
        graph.entities = [e for e in graph.entities 
                         if e.name not in entity_names]
        graph.relations = [r for r in graph.relations 
                         if r.from_ not in entity_names and 
                         r.to not in entity_names]
        await self.save_graph(graph)

    async def delete_observations(self, deletions: List[Dict[str, Any]]) -> None:
        graph = await self.load_graph()
        
        for deletion in deletions:
            entity = next((e for e in graph.entities 
                          if e.name == deletion["entityName"]), None)
            if entity:
                entity.observations = [o for o in entity.observations 
                                     if o not in deletion["observations"]]
                
        await self.save_graph(graph)

    async def delete_relations(self, relations: List[Relation]) -> None:
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

    async def open_nodes(self, names: List[str]) -> KnowledgeGraph:
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
    logger.info(f"Starting Memory MCP Server with memory path: {memory_path} on port: {port}")
    
    graph_manager = KnowledgeGraphManager(memory_path)
    app = Server("memory-manager")

    @app.list_tools()
    async def handle_list_tools() -> List[types.Tool]:
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
        arguments: Dict[str, Any] | None
    ) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        try:
            if name == "read_graph":
                result = await graph_manager.read_graph()
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "entities": [vars(e) for e in result.entities],
                        "relations": [vars(r) for r in result.relations]
                    }, indent=2)
                )]
            
            if not arguments:
                raise ValueError("Missing arguments")
                
            if name == "create_entities":
                entities = [Entity(**e) for e in arguments["entities"]]
                result = await graph_manager.create_entities(entities)
                return [types.TextContent(
                    type="text",
                    text=json.dumps([vars(e) for e in result], indent=2)
                )]
                
            elif name == "create_relations":
                relations = [Relation(**r) for r in arguments["relations"]]
                result = await graph_manager.create_relations(relations)
                return [types.TextContent(
                    type="text",
                    text=json.dumps([vars(r) for r in result], indent=2)
                )]
                
            elif name == "add_observations":
                result = await graph_manager.add_observations(arguments["observations"])
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
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
                    }, indent=2)
                )]
                
            elif name == "open_nodes":
                result = await graph_manager.open_nodes(arguments["names"])
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "entities": [vars(e) for e in result.entities],
                        "relations": [vars(r) for r in result.relations]
                    }, indent=2)
                )]
            
            else:
                raise ValueError(f"Unknown tool: {name}")
            
        except Exception as e:
            logger.error(f"Error in tool {name}: {str(e)}")
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

if __name__ == "__main__":
    import asyncio
    import argparse
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='MCP Memory Server')
    parser.add_argument('--port', type=int, default=8080, help='服务器端口号')
    parser.add_argument('--memory-path', type=str, help='内存文件路径')
    
    args = parser.parse_args()
    
    # 获取内存文件路径
    default_memory_path = Path(__file__).parent / "memory.json"
    memory_path = args.memory_path or os.getenv("MEMORY_FILE_PATH", default_memory_path)
    
    if not Path(memory_path).is_absolute():
        memory_path = Path(__file__).parent / memory_path
        
    asyncio.run(main(str(memory_path), args.port))
