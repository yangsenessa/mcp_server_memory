// 工具函数：处理 SSE 连接
async function connectSSE(port) {
  const url = `http://localhost:${port}/sse`
  console.log(`连接到 SSE 服务器: ${url}`)

  let sessionId = null 
  let toolsRequested = false

  return new Promise((resolve, reject) => {
    const eventSource = new EventSource(url)

    // 连接打开时的处理
    eventSource.onopen = () => {
      console.log('SSE 连接已建立')
    }

    // 连接错误处理
    eventSource.onerror = (error) => {
      console.error('SSE 连接错误:', error)
      eventSource.close()
      reject(error)
    }

    // 处理 endpoint 事件
    eventSource.addEventListener('endpoint', async (event) => {
      console.log(`收到事件类型 event: endpoint`)
      console.log(`事件数据: ${event.data}`)
      
      const sessionUri = event.data
      const sessionIdMatch = sessionUri.match(/session_id=([^&]+)/)
      if (sessionIdMatch) {
        sessionId = sessionIdMatch[1]
        console.log(`获取到会话 ID: ${sessionId}`)

        // 获取到 sessionId 后，发送初始化请求
        try {
          const initResponse = await initializeSession(port, sessionId)
          console.log('初始化响应完成，状态:', initResponse.status)

          // 发送 initialized 通知
          toolsRequested = await handleInitialized(port, sessionId, toolsRequested)
        } catch (error) {
          console.error('初始化会话失败:', error)
          eventSource.close()
          reject(error)
        }
      }
    })

    // 处理 message 事件
    eventSource.addEventListener('message', async (event) => {
      console.log(`收到事件类型 event: message`)
      console.log(`事件数据: ${event.data}`)
      
      try {
        const message = JSON.parse(event.data)
        console.log('收到服务器消息:', message)

        // 检查是否是初始化完成的消息
        if (
          message.jsonrpc === '2.0' &&
          message.id === 1 &&
          message.result
        ) {
          initialized = true
          console.log('初始化完成，现在可以发送其他请求')

          // 发送 initialized 通知
          toolsRequested = await handleInitialized(port, sessionId, toolsRequested)
        }
      } catch (error) {
        console.error('解析消息失败:', error)
      }
    })

    // 可以添加关闭连接的逻辑
    // eventSource.close() 在适当的时候调用
  })
}

// 初始化会话
async function initializeSession (port, sessionId) {
  console.log(`初始化会话 ${sessionId}`)
  const jsonRpcRequest = {
    jsonrpc: '2.0',
    method: 'initialize',
    id: 1,
    params: {
      protocolVersion: '0.1.0',
      capabilities: {},
      clientInfo: {
        name: 'JavaScript MCP Client',
        version: '1.0.0'
      }
    }
  }

  const response = await fetch(
    `http://localhost:${port}/messages/?session_id=${sessionId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(jsonRpcRequest)
    }
  )

  if (!response.ok) {
    throw new Error(`初始化会话失败: ${response.status} ${response.statusText}`)
  }

  console.log('初始化请求已发送，状态:', response.status)

  // 读取响应内容并等待响应完成
  const responseText = await response.text()
  console.log('初始化响应内容:', responseText)

  // 添加额外延迟，确保连接完全关闭
  await new Promise(resolve => setTimeout(resolve, 3000))
  console.log('初始化请求已完成并断开连接')

  return { status: response.status, data: responseText }
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

// 发送 initialized 通知
async function sendInitializedNotification (port, sessionId) {
  console.log(`发送 initialized 通知，会话 ${sessionId}`)
  const jsonRpcRequest = {
    jsonrpc: '2.0',
    method: 'notifications/initialized',
    // 注意：通知没有 id 字段
    params: {}
  }

  const response = await fetch(
    `http://localhost:${port}/messages/?session_id=${sessionId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(jsonRpcRequest)
    }
  )

  if (!response.ok) {
    throw new Error(
      `发送 initialized 通知失败: ${response.status} ${response.statusText}`
    )
  }

  console.log('initialized 通知已发送，状态:', response.status)

  // 读取响应内容并等待响应完成
  const responseText = await response.text()
  console.log('initialized 响应内容:', responseText)

  // 添加额外延迟，确保连接完全关闭
  await new Promise(resolve => setTimeout(resolve, 3000))
  console.log('initialized 通知已完成并断开连接')

  return { status: response.status, data: responseText }
}

// 获取工具列表
async function getToolsList (port, sessionId) {
  console.log(`获取工具列表，会话 ${sessionId}`)
  const jsonRpcRequest = {
    jsonrpc: '2.0',
    method: 'tools/list',
    id: 2,
    params: {}
  }

  const response = await fetch(
    `http://localhost:${port}/messages/?session_id=${sessionId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(jsonRpcRequest)
    }
  )

  if (!response.ok) {
    throw new Error(
      `获取工具列表失败: ${response.status} ${response.statusText}`
    )
  }

  console.log('工具列表请求已发送，状态:', response.status)

  return { status: response.status }
}

// 调用 fetch 工具
async function callFetchTool (port, sessionId, url) {
  console.log(`调用 fetch 工具，URL: ${url}`)
  const jsonRpcRequest = {
    jsonrpc: '2.0',
    method: 'call_tool',
    id: 3,
    params: {
      name: 'fetch',
      arguments: {
        url: url
      }
    }
  }

  const response = await fetch(
    `http://localhost:${port}/messages/?session_id=${sessionId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(jsonRpcRequest)
    }
  )

  if (!response.ok) {
    throw new Error(`调用工具失败: ${response.status} ${response.statusText}`)
  }

  console.log('工具调用请求已发送，状态:', response.status)

  // 读取响应内容并等待响应完成
  const responseText = await response.text()
  console.log('工具调用响应内容:', responseText)

  // 添加额外延迟，确保连接完全关闭
  await new Promise(resolve => setTimeout(resolve, 3000))
  console.log('工具调用请求已完成并断开连接')

  return { status: response.status, data: responseText }
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
