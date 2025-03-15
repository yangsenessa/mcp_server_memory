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

// Example usage
testSSEServer('http://localhost:8000/sse')

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
  
  // 读取响应内容并等待响应完成
  const responseText = await response.text()
  console.log('工具列表响应内容:', responseText)
  
  // 添加额外延迟，确保连接完全关闭
  await new Promise(resolve => setTimeout(resolve, 3000))
  console.log('工具列表请求已完成并断开连接')
  
  return { status: response.status, data: responseText }
}

// 连接到 SSE 服务器并处理事件
async function connectSSE (port) {
  const url = `http://localhost:${port}/sse`
  console.log(`连接到 SSE 服务器: ${url}`)

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'text/event-stream'
      }
    })

    if (!response.ok) {
      throw new Error(`连接 SSE 服务器失败: ${response.statusText}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    let buffer = ''
    let sessionId = null
    let initialized = false
    let toolsRequested = false

    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      let endOfLineIndex
      while ((endOfLineIndex = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, endOfLineIndex + 1)
        buffer = buffer.slice(endOfLineIndex + 1)

        // 处理事件类型
        if (line.startsWith('event: ')) {
          const eventType = line.slice(7).trim()
          console.log(`收到事件类型: ${eventType}`)

          // 等待下一行获取数据
          const dataLineIndex = buffer.indexOf('\n')
          if (dataLineIndex >= 0 && buffer.startsWith('data: ')) {
            const dataLine = buffer.slice(0, dataLineIndex + 1)
            buffer = buffer.slice(dataLineIndex + 1)

            const data = dataLine.slice(6).trim()
            console.log(`事件数据: ${data}`)

            if (eventType === 'endpoint') {
              // 从 endpoint 事件中提取 session_id
              const sessionUri = data
              const sessionIdMatch = sessionUri.match(/session_id=([^&]+)/)
              if (sessionIdMatch) {
                sessionId = sessionIdMatch[1]
                console.log(`获取到会话 ID: ${sessionId}`)

                // 获取到 sessionId 后，发送初始化请求，并等待完全完成
                try {
                  const initResponse = await initializeSession(port, sessionId)
                  console.log('初始化响应完成，状态:', initResponse.status)
                  
                  // 初始化完成后，标记为已初始化
                  initialized = true
                  
                  // 在初始化完成后，请求工具列表
                  if (!toolsRequested) {
                    toolsRequested = true
                    try {
                      console.log('开始请求工具列表...')
                      const toolsResponse = await getToolsList(port, sessionId)
                      console.log('工具列表响应状态:', toolsResponse.status)
                    } catch (error) {
                      console.error('获取工具列表失败:', error)
                    }
                  }
                } catch (error) {
                  console.error('初始化会话失败:', error)
                }
              }
            } else if (eventType === 'message') {
              // 处理服务器发送的消息
              try {
                const message = JSON.parse(data)
                console.log('收到服务器消息:', message)

                // 检查是否是初始化完成的消息
                if (
                  message.jsonrpc === '2.0' &&
                  message.id === 1 &&
                  message.result
                ) {
                  initialized = true
                  console.log('初始化完成，现在可以发送其他请求')

                  // 初始化完成后，请求工具列表，但确保只请求一次
                  if (!toolsRequested && sessionId) {
                    toolsRequested = true
                    try {
                      // 添加更长的延迟，确保服务器完全准备好
                      await new Promise(resolve => setTimeout(resolve, 1000))
                      const toolsResponse = await getToolsList(port, sessionId)
                      console.log('工具列表响应状态:', toolsResponse.status)
                    } catch (error) {
                      console.error('获取工具列表失败:', error)
                    }
                  }
                }
              } catch (error) {
                console.error('解析消息失败:', error)
              }
            }
          }
        } else if (line.trim() && line.startsWith('data: ')) {
          // 处理没有明确事件类型的数据行
          const data = line.slice(6).trim()
          console.log('收到数据:', data)
          try {
            const jsonData = JSON.parse(data)
            console.log('解析的JSON数据:', jsonData)

            // 如果这是初始化响应，标记初始化完成
            if (
              jsonData.jsonrpc === '2.0' &&
              jsonData.id === 1 &&
              jsonData.result
            ) {
              initialized = true
              console.log('初始化完成，现在可以发送其他请求')

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
            }
          } catch (error) {
            // 不是JSON数据，忽略错误
          }
        }
      }
    }
  } catch (error) {
    console.error('SSE连接错误:', error)
    throw error
  }
}

// 初始化会话
async function initializeSession (port, sessionId) {
  console.log(`初始化会话 ${sessionId}`)
  const jsonRpcRequest = {
    jsonrpc: '2.0',
    method: 'initialize',
    id: 1,
    params: {
      protocolVersion: '0.1.0', // 添加协议版本
      capabilities: {}, // 添加能力对象
      clientInfo: {
        // 添加客户端信息
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
