# 1. 获取可用工具列表
```
curl -X GET http://localhost:8000/tools
```

# 2. 调用加法工具

```
curl -X POST http://localhost:8000/tool/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "add",
    "tool_args": {
      "a": 5,
      "b": 3
    }
  }'
```

# 3. 获取个性化问候
```
curl -X POST http://localhost:8000/tool/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "greeting:/张三",
    "tool_args": {}
  }'
```