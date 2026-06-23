async function readErrorMessage(response) {
  const text = await response.text()

  if (!text) {
    return `请求失败：${response.status}`
  }

  try {
    const body = JSON.parse(text)
    const detail = body.detail || body.message || body.error

    if (typeof detail === 'string') {
      try {
        const nested = JSON.parse(detail)
        return nested.detail || detail
      } catch {
        return detail
      }
    }

    return JSON.stringify(body)
  } catch {
    return text
  }
}

export async function evaluateModel(files) {
  const formData = new FormData()

  Array.from(files).forEach(file => {
    formData.append('files', file, file.webkitRelativePath || file.relativePath || file.name)
  })

  const response = await fetch('/api/model-evaluation', {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }

  return await response.json()
}

export async function evaluateModelByPath(dataPath) {
  const response = await fetch('/api/model-evaluation-path', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ dataPath })
  })

  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }

  return await response.json()
}
