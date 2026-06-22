export async function listPatients(params = {}) {
  const query = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  })

  const queryString = query.toString()
  const url = queryString ? `/api/patients?${queryString}` : '/api/patients'

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function createPatient(patient) {
  const response = await fetch('/api/patients', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(patient)
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function updatePatient(patientId, patient) {
  const response = await fetch(`/api/patients/${patientId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(patient)
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function createPatientRecord(patientId, record) {
  const response = await fetch(`/api/patients/${patientId}/records`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(record)
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function deletePatient(patientId) {
  const response = await fetch(`/api/patients/${patientId}`, {
    method: 'DELETE'
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  return await response.json()
}

export async function findPatientByExactName(name) {
  const response = await listPatients({ keyword: name })
  const patients = response.data || []

  return patients.find(patient => patient.name === name) || null
}
