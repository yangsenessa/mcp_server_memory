// 工具函数：处理 SSE 连接
async function connectSSE (port) {
  const url = `http://localhost:${port}/sse`
  console.log(`连接到 SSE 服务器: ${url}`)

  let sessionId = null
  let initialized = false
  let toolsRequested = false

  return new Promise((resolve, reject) => {
    const eventSource = new EventSource(url)

    // 连接打开时的处理
    eventSource.onopen = () => {
      console.log('SSE 连接已建立')
    }

    // 连接错误处理
    eventSource.onerror = error => {
      console.error('SSE 连接错误:', error)
      eventSource.close()
      reject(error)
    }

    // 处理 endpoint 事件
    eventSource.addEventListener('endpoint', async event => {
      console.log(`收到事件类型 event: endpoint`)
      console.log(`事件数据: ${event.data}`)

      const sessionUri = event.data
      const sessionIdMatch = sessionUri.match(/session_id=([^&]+)/)
      if (sessionIdMatch) {
        sessionId = sessionIdMatch[1]
        console.log(`获取到会话 ID: ${sessionId}`)

        // 获取到 sessionId 后，发送初始化请求（仅当未初始化时）
        if (!initialized) {
          try {
            const initResponse = await initializeSession(port, sessionId)
            console.log('初始化响应完成，状态:', initResponse.status)
            // 不在这里设置 initialized，而是等待 message 事件确认
          } catch (error) {
            console.error('初始化会话失败:', error)
            eventSource.close()
            reject(error)
          }
        }
      }
    })

    // 处理 message 事件
    eventSource.addEventListener('message', async event => {
      console.log(`收到事件类型 event: message`)
      console.log(`事件数据: ${event.data}`)

      try {
        const message = JSON.parse(event.data)
        console.log('收到服务器消息:', message)

        // 检查是否是初始化完成的消息
        if (
          message.jsonrpc === '2.0' &&
          message.id === 1 &&
          message.result &&
          !initialized
        ) {
          initialized = true
          console.log('初始化完成，现在可以发送其他请求')

          // 发送 initialized 通知
          toolsRequested = await handleInitialized(
            port,
            sessionId,
            toolsRequested
          )
        }

        if (message.jsonrpc === '2.0' && message.result?.serverInfo) {
          const { name, version } = message.result.serverInfo
          console.log(`##服务器信息: ${name} ${version}`)
        }

        if (message.jsonrpc === '2.0' && message.result?.tools) {
          const tools = message.result.tools
          console.log('##可用工具:', tools)
        }
      } catch (error) {
        console.error('解析消息失败:', error)
      }
    })

    // 可以添加关闭连接的逻辑
    // eventSource.close() 在适当的时候调用
  })
}

// 通用的 JSON-RPC 请求函数
async function sendJsonRpcRequest (port, sessionId, method, params, id = null) {
  console.log(`发送 ${method} 请求，会话 ${sessionId}`)

  const jsonRpcRequest = {
    jsonrpc: '2.0',
    method: method,
    params: params || {}
  }

  // 只有非通知类请求才需要 id
  if (id !== null) {
    jsonRpcRequest.id = id
  }

  const url = `http://localhost:${port}/messages/?session_id=${sessionId}`
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(jsonRpcRequest)
  })

  if (!response.ok) {
    throw new Error(
      `${method} 请求失败: ${response.status} ${response.statusText}`
    )
  }

  console.log(`${method} 请求已发送，状态:`, response.status)

  // 读取响应内容
  const responseText = await response.text()
  console.log(`${method} 响应内容:`, responseText)

  // 添加额外延迟，确保连接完全关闭
  await new Promise(resolve => setTimeout(resolve, 3000))
  console.log(`${method} 请求已完成并断开连接`)

  return { status: response.status, data: responseText }
}

// 初始化会话 - 使用通用请求函数
async function initializeSession (port, sessionId) {
  return sendJsonRpcRequest(
    port,
    sessionId,
    'initialize',
    {
      protocolVersion: '0.1.0',
      capabilities: {},
      clientInfo: {
        name: 'JavaScript MCP Client',
        version: '1.0.0'
      }
    },
    1
  )
}

// 发送 initialized 通知 - 使用通用请求函数
async function sendInitializedNotification (port, sessionId) {
  return sendJsonRpcRequest(
    port,
    sessionId,
    'notifications/initialized',
    {},
    null
  )
}

// 获取工具列表 - 使用通用请求函数
async function getToolsList (port, sessionId) {
  return sendJsonRpcRequest(port, sessionId, 'tools/list', {}, 2)
}

// 调用 fetch 工具 - 使用通用请求函数
async function callFetchTool (port, sessionId, url) {
  return sendJsonRpcRequest(
    port,
    sessionId,
    'call_tool',
    {
      name: 'fetch',
      arguments: {
        url: url
      }
    },
    3
  )
}

// 处理初始化完成后的操作
async function handleInitialized (port, sessionId, toolsRequested) {
  try {
    await sendInitializedNotification(port, sessionId)
    console.log('initialized 通知已发送')

    // 初始化完成后，请求工具列表，但确保只请求一次
    if (!toolsRequested && sessionId) {
      toolsRequested = true
      try {
        // 添加延迟，确保服务器完全准备好
        await new Promise(resolve => setTimeout(resolve, 500))
        const toolsResponse = await getToolsList(port, sessionId)
        console.log('工具列表响应状态:', toolsResponse.status)
      } catch (error) {
        console.error('获取工具列表失败:', error)
      }
    }
  } catch (error) {
    console.error('发送 initialized 通知失败:', error)
  }
  return toolsRequested
}

// 主函数
;(async () => {
  const port = 8000
  try {
    // 连接到 SSE 服务器，它会自动处理后续流程
    await connectSSE(port)
  } catch (error) {
    console.error('主流程错误:', error)
  }
})()
