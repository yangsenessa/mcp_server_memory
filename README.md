 
python init_env.py

.venv\Scripts\activate
 
python mcp_server.py --transport sse --port 8000

#build
cat memory_mcp.json | python build.py