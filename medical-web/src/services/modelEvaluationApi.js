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
    throw new Error(`请求失败：${response.status}`)
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
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}
