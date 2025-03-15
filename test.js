async function testSSEServer (url) {
  const response = await fetch(url, {
    headers: {
      Accept: 'text/event-stream'
    }
  })

  if (!response.ok) {
    throw new Error(`Failed to connect to SSE server: ${response.statusText}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')

  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    let endOfLineIndex
    while ((endOfLineIndex = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, endOfLineIndex + 1)
      buffer = buffer.slice(endOfLineIndex + 1)

      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()
        console.log('Received SSE message:', data)
      }
    }
  }
}

// 在收到初始化响应后发送 initialized 通知
async function sendInitializedNotification(port, sessionId) {
  console.log(`发送 initialized 通知，会话 ${sessionId}`);
  const notification = {
    jsonrpc: "2.0",
    method: "initialized",
    params: {}
  };

  const response = await fetch(`http://localhost:${port}/messages/?session_id=${sessionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(notification)
  });

  if (!response.ok) {
    throw new Error(`发送 initialized 通知失败: ${response.status} ${response.statusText}`);
  }
  
  console.log('initialized 通知已发送，状态:', response.status);
  return response;
}

// Example usage
testSSEServer('http://localhost:8000/sse')

// 首先建立 SSE 连接
async function connectSSE(port) {
  const url = `http://localhost:${port}/sse`;
  console.log(`连接到 SSE 服务器: ${url}`);
  
  const response = await fetch(url, {
    headers: {
      Accept: 'text/event-stream'
    }
  });

  if (!response.ok) {
    throw new Error(`无法连接到 SSE 服务器: ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  
  let buffer = '';
  let sessionId = null;
  
  // 处理 SSE 事件流
  (async () => {
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        let endOfLineIndex;
        while ((endOfLineIndex = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, endOfLineIndex + 1);
          buffer = buffer.slice(endOfLineIndex + 1);
          
          if (line.startsWith('event: endpoint')) {
            // 下一行将包含 session_id
            continue;
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            console.log('收到 SSE 消息:', data);
            
            // 检查是否是端点消息（包含 session_id）
            if (data.includes('session_id=')) {
              const urlParts = data.split('?');
              if (urlParts.length > 1) {
                const params = new URLSearchParams(urlParts[1]);
                sessionId = params.get('session_id');
                console.log('获取到 session_id:', sessionId);
                
                // 一旦获取到 session_id，立即初始化会话
                if (sessionId) {
                  await initializeSession(port, sessionId);
                }
              }
            } else {
              // 尝试解析 JSON 响应
              try {
                const jsonData = JSON.parse(data);
                console.log('解析的 JSON 数据:', jsonData);
                
                // 检查是否收到了初始化响应
                if (jsonData.id === 1 && jsonData.result) {
                  console.log('服务器初始化完成，现在发送 initialized 通知');
                  await sendInitializedNotification(port, sessionId);
                  // 只有在发送 initialized 通知后才获取工具列表
                  await getToolsList(port, sessionId);
                }
              } catch (e) {
                // 不是 JSON 数据，忽略
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('SSE 流处理错误:', error);
    }
  })();
  
  return response;
}

// 发送初始化请求
async function initializeSession(port, sessionId) {
  console.log(`初始化会话 ${sessionId}`);
  const initRequest = {
    jsonrpc: "2.0",
    method: "initialize",
    id: 1,
    params: {
      protocolVersion: "0.1.0",
      capabilities: {},
      clientInfo: {
        name: "test-client",
        version: "1.0.0"
      }
    }
  };

  const response = await fetch(`http://localhost:${port}/messages/?session_id=${sessionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(initRequest)
  });

  if (!response.ok) {
    throw new Error(`初始化失败: ${response.status} ${response.statusText}`);
  }
  
  console.log('初始化请求已发送，状态:', response.status);
  return response;
}

// 获取工具列表
async function getToolsList(port, sessionId) {
  console.log(`获取工具列表，会话 ${sessionId}`);
  const jsonRpcRequest = {
    jsonrpc: "2.0",
    method: "tools/list",
    id: 2,
    params: {}
  };

  const response = await fetch(`http://localhost:${port}/messages/?session_id=${sessionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(jsonRpcRequest)
  });

  if (!response.ok) {
    throw new Error(`获取工具列表失败: ${response.status} ${response.statusText}`);
  }
  
  console.log('工具列表请求已发送，状态:', response.status);
  return response;
}

// 完整的会话工作流
async function runSessionWorkflow(port, sessionId) {
  try {
    // 1. 发送初始化请求
    const initResponse = await initializeSession(port, sessionId);
    console.log('初始化响应状态:', initResponse.status);
    
    // 不要在这里立即获取工具列表
    // 而是等待服务器发送 initialized 响应
    // 这将在 SSE 事件处理中完成
  } catch (error) {
    console.error('会话工作流错误:', error);
  }
}

// 主函数
(async () => {
  const port = 8000;
  try {
    // 连接到 SSE 服务器，它会自动处理后续流程
    await connectSSE(port);
  } catch (error) {
    console.error('主流程错误:', error);
  }
})();
