export async function listOperationLogs() {
  const response = await fetch('/api/operation-logs')

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function createOperationLog(log) {
  const response = await fetch('/api/operation-logs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(log)
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function deleteOperationLog(logId) {
  const response = await fetch(`/api/operation-logs/${logId}`, {
    method: 'DELETE'
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function clearOperationLogs() {
  const response = await fetch('/api/operation-logs', {
    method: 'DELETE'
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function safeCreateOperationLog(log) {
  try {
    await createOperationLog(log)
    window.dispatchEvent(new CustomEvent('operation-log-changed'))
  } catch (error) {
    console.warn('操作日志写入失败', error)
  }
}
