<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { createPatient, deletePatient, listPatients, updatePatient } from '../services/patientApi'
import { safeCreateOperationLog } from '../services/operationLogApi'

const patients = ref([])
const loading = ref(false)
const submitting = ref(false)
const deletingId = ref(null)
const editingId = ref(null)
const savingId = ref(null)
const errorMessage = ref('')
const createMessage = ref('')
const deleteMessage = ref('')
const editMessage = ref('')

const createForm = ref({
  name: '',
  gender: '男',
  age: ''
})

const searchForm = ref({
  keyword: '',
  gender: '',
  result: ''
})

const sortState = ref({
  sortBy: 'id',
  order: 'desc'
})

const editForm = ref({
  name: '',
  gender: '男',
  age: ''
})

async function loadPatients() {
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await listPatients({
      keyword: searchForm.value.keyword,
      gender: searchForm.value.gender,
      result: searchForm.value.result,
      sortBy: sortState.value.sortBy,
      order: sortState.value.order
    })

    patients.value = response.data || []
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function handleCreatePatient() {
  const name = createForm.value.name.trim()
  const age = Number(createForm.value.age)

  if (!name) {
    createMessage.value = '请填写患者姓名'
    return
  }

  if (!Number.isInteger(age) || age < 0 || age > 120) {
    createMessage.value = '请填写 0 到 120 之间的整数年龄'
    return
  }

  submitting.value = true
  createMessage.value = ''

  try {
    await createPatient({
      name,
      gender: createForm.value.gender,
      age
    })

    createForm.value = {
      name: '',
      gender: '男',
      age: ''
    }
    createMessage.value = '患者已添加'
    await safeCreateOperationLog({
      action: '添加患者',
      detail: `添加患者 ${name}`
    })
    await loadPatients()
  } catch (error) {
    createMessage.value = error.message
  } finally {
    submitting.value = false
  }
}

async function handleDeletePatient(patient) {
  const confirmed = window.confirm(`确认删除患者 ${patient.name} 吗？该患者的检测记录也会一起删除。`)

  if (!confirmed) {
    return
  }

  deletingId.value = patient.id
  deleteMessage.value = ''

  try {
    await deletePatient(patient.id)
    deleteMessage.value = '患者已删除'
    await safeCreateOperationLog({
      action: '删除患者',
      detail: `删除患者 ${patient.name}`
    })
    await loadPatients()
  } catch (error) {
    deleteMessage.value = error.message
  } finally {
    deletingId.value = null
  }
}

function startEditPatient(patient) {
  editingId.value = patient.id
  editMessage.value = ''
  editForm.value = {
    name: patient.name,
    gender: patient.gender,
    age: patient.age
  }
}

async function saveEditPatient(patient) {
  const name = editForm.value.name.trim()
  const age = Number(editForm.value.age)

  if (!name) {
    editMessage.value = '请填写患者姓名'
    return
  }

  if (!Number.isInteger(age) || age < 0 || age > 120) {
    editMessage.value = '请填写 0 到 120 之间的整数年龄'
    return
  }

  savingId.value = patient.id
  editMessage.value = ''

  try {
    await updatePatient(patient.id, {
      name,
      gender: editForm.value.gender,
      age
    })

    editingId.value = null
    editMessage.value = '患者信息已更新'
    await safeCreateOperationLog({
      action: '编辑患者',
      detail: `更新患者 ${patient.name} 的基本信息`
    })
    await loadPatients()
  } catch (error) {
    editMessage.value = error.message
  } finally {
    savingId.value = null
  }
}

function changeSort(sortBy) {
  if (sortState.value.sortBy === sortBy) {
    sortState.value.order = sortState.value.order === 'asc' ? 'desc' : 'asc'
  } else {
    sortState.value.sortBy = sortBy
    sortState.value.order = 'asc'
  }

  loadPatients()
}

function getSortIcon(sortBy) {
  if (sortState.value.sortBy !== sortBy) {
    return '↕'
  }

  return sortState.value.order === 'asc' ? '↑' : '↓'
}

function handleSearch() {
  loadPatients()
}

function resetSearch() {
  searchForm.value = {
    keyword: '',
    gender: '',
    result: ''
  }

  loadPatients()
}

function handlePatientDataChanged() {
  loadPatients()
}

function formatConfidence(value) {
  if (value === null || value === undefined) {
    return '暂无'
  }

  return Number(value).toFixed(4)
}

function formatTime(value) {
  if (!value) {
    return '暂无'
  }

  return value.replace('T', ' ').slice(0, 19)
}

onMounted(() => {
  loadPatients()
  window.addEventListener('patient-data-changed', handlePatientDataChanged)
})

onBeforeUnmount(() => {
  window.removeEventListener('patient-data-changed', handlePatientDataChanged)
})
</script>

<template>
  <section class="patient-page">
    <div class="table-area">
      <div class="table-title">
        <span>共 {{ patients.length }} 条</span>
        <span v-if="loading">加载中...</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
        <span v-if="deleteMessage" class="message-text">{{ deleteMessage }}</span>
        <span v-if="editMessage" class="message-text">{{ editMessage }}</span>
      </div>

      <table class="patient-table">
        <thead>
          <tr>
            <th>
              <button class="sortable-header" :class="{ active: sortState.sortBy === 'name' }"
                @click="changeSort('name')">
                <span>姓名</span>
                <span class="sort-indicator">{{ getSortIcon('name') }}</span>
              </button>
            </th>
            <th>
              <button class="sortable-header" :class="{ active: sortState.sortBy === 'gender' }"
                @click="changeSort('gender')">
                <span>性别</span>
                <span class="sort-indicator">{{ getSortIcon('gender') }}</span>
              </button>
            </th>
            <th>
              <button class="sortable-header" :class="{ active: sortState.sortBy === 'age' }"
                @click="changeSort('age')">
                <span>年龄</span>
                <span class="sort-indicator">{{ getSortIcon('age') }}</span>
              </button>
            </th>
            <th>
              <button class="sortable-header" :class="{ active: sortState.sortBy === 'latestResult' }"
                @click="changeSort('latestResult')">
                <span>最近检测结果</span>
                <span class="sort-indicator">{{ getSortIcon('latestResult') }}</span>
              </button>
            </th>
            <th>
              <button class="sortable-header" :class="{ active: sortState.sortBy === 'latestConfidence' }"
                @click="changeSort('latestConfidence')">
                <span>阳性概率</span>
                <span class="sort-indicator">{{ getSortIcon('latestConfidence') }}</span>
              </button>
            </th>
            <th>
              <button class="sortable-header" :class="{ active: sortState.sortBy === 'latestTestedAt' }"
                @click="changeSort('latestTestedAt')">
                <span>最近检测时间</span>
                <span class="sort-indicator">{{ getSortIcon('latestTestedAt') }}</span>
              </button>
            </th>
            <th>操作</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="patient in patients" :key="patient.id">
            <td>
              <input v-if="editingId === patient.id" v-model="editForm.name" class="table-edit-input">
              <template v-else>{{ patient.name }}</template>
            </td>
            <td>
              <select v-if="editingId === patient.id" v-model="editForm.gender" class="table-edit-input">
                <option value="男">男</option>
                <option value="女">女</option>
              </select>
              <template v-else>{{ patient.gender }}</template>
            </td>
            <td>
              <input v-if="editingId === patient.id" v-model="editForm.age" class="table-edit-input" type="number"
                min="0" max="120">
              <template v-else>{{ patient.age }}</template>
            </td>
            <td>{{ patient.latestResult || '暂无' }}</td>
            <td>{{ formatConfidence(patient.latestConfidence) }}</td>
            <td>{{ formatTime(patient.latestTestedAt) }}</td>
            <td>
              <button v-if="editingId === patient.id" class="text-button" :disabled="savingId === patient.id"
                @click="saveEditPatient(patient)">
                {{ savingId === patient.id ? '保存中...' : '保存' }}
              </button>
              <button v-else class="text-button" @click="startEditPatient(patient)">编辑</button>
              <button class="text-button danger" :disabled="deletingId === patient.id" @click="handleDeletePatient(patient)">
                {{ deletingId === patient.id ? '删除中...' : '删除' }}
              </button>
            </td>
          </tr>

          <tr v-if="!loading && patients.length === 0">
            <td colspan="7" class="empty-cell">暂无患者数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <aside class="side-panel">
      <section class="panel-section">
        <div class="panel-header">
          <h2>添加患者</h2>
        </div>

        <div class="form-row">
          <label>姓名</label>
          <input v-model="createForm.name" placeholder="患者姓名">
        </div>

        <div class="form-row">
          <label>性别</label>
          <div class="option-group two">
            <button type="button" :class="{ active: createForm.gender === '男' }" @click="createForm.gender = '男'">
              男
            </button>
            <button type="button" :class="{ active: createForm.gender === '女' }" @click="createForm.gender = '女'">
              女
            </button>
          </div>
        </div>

        <div class="form-row">
          <label>年龄</label>
          <input v-model="createForm.age" type="number" min="0" max="120" placeholder="患者年龄">
        </div>

        <div class="form-actions">
          <span></span>
          <button class="primary-button" :disabled="submitting" @click="handleCreatePatient">
            {{ submitting ? '添加中...' : '添加患者' }}
          </button>
        </div>
        <p v-if="createMessage" class="message-text">{{ createMessage }}</p>
      </section>

      <section class="panel-section">
        <div class="panel-header">
          <h2>查询患者</h2>
        </div>

        <div class="form-row">
          <label>关键词</label>
          <input v-model="searchForm.keyword" placeholder="患者姓名">
        </div>

        <div class="form-row">
          <label>性别</label>
          <div class="option-group three">
            <button type="button" :class="{ active: searchForm.gender === '' }" @click="searchForm.gender = ''">
              全部
            </button>
            <button type="button" :class="{ active: searchForm.gender === '男' }" @click="searchForm.gender = '男'">
              男
            </button>
            <button type="button" :class="{ active: searchForm.gender === '女' }" @click="searchForm.gender = '女'">
              女
            </button>
          </div>
        </div>

        <div class="form-row">
          <label>检测结果</label>
          <div class="option-group four">
            <button type="button" :class="{ active: searchForm.result === '' }" @click="searchForm.result = ''">
              全部
            </button>
            <button type="button" :class="{ active: searchForm.result === '患病' }" @click="searchForm.result = '患病'">
              患病
            </button>
            <button type="button" :class="{ active: searchForm.result === '不患病' }" @click="searchForm.result = '不患病'">
              不患病
            </button>
            <button type="button" :class="{ active: searchForm.result === 'NO_RECORD' }" @click="searchForm.result = 'NO_RECORD'">
              未检测
            </button>
          </div>
        </div>

        <div class="form-actions two">
          <span></span>
          <button class="primary-button" @click="handleSearch">搜索</button>
          <button class="secondary-button" @click="resetSearch">重置</button>
        </div>
      </section>
    </aside>
  </section>
</template>

<style scoped>
.patient-page {
  min-height: calc(100vh - 104px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(320px, 23vw, 380px);
  gap: 28px;
}

.table-area {
  min-width: 0;
  overflow-x: auto;
  background: var(--color-surface);
}

.table-title {
  min-height: 46px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-title h2 {
  margin: 0;
  font-size: 20px;
}

.table-title span {
  color: var(--color-muted);
  font-size: 14px;
}

.patient-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  font-size: 14px;
}

.patient-table th,
.patient-table td {
  height: 46px;
  padding: 0 14px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.patient-table th {
  color: #334155;
  font-weight: 600;
  background: var(--color-surface-soft);
  padding: 0;
}

.patient-table th:last-child {
  padding: 0 14px;
}

.patient-table td {
  color: var(--color-text);
}

.patient-table tbody tr {
  transition: background 0.14s ease;
}

.patient-table tbody tr:hover {
  background: #f8fafc;
}

.table-edit-input {
  width: 100%;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--color-border-strong);
  box-sizing: border-box;
}

.sortable-header {
  width: 100%;
  height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  padding: 0 14px;
  border: 1px solid transparent;
  background: transparent;
  color: #334155;
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}

.sortable-header:hover,
.sortable-header.active {
  color: var(--color-primary);
}

.sort-indicator {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  color: #94a3b8;
}

.sortable-header:hover .sort-indicator,
.sortable-header.active .sort-indicator {
  border-color: var(--color-primary-border);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.text-button {
  margin-right: 8px;
  padding: 4px 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease;
}

.text-button:hover {
  border-color: var(--color-primary-border);
  background: var(--color-primary-soft);
}

.text-button.danger {
  color: var(--color-danger);
}

.text-button.danger:hover {
  border-color: #fecaca;
  background: var(--color-danger-soft);
}

.side-panel {
  min-width: 0;
  padding-left: 28px;
  border-left: 1px solid var(--color-border);
  font-size: 14px;
}

.panel-section + .panel-section {
  margin-top: 24px;
  padding-top: 22px;
  border-top: 1px solid var(--color-border);
}

.panel-header h2 {
  margin: 0 0 16px;
  font-size: 18px;
}

.form-row {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.form-row label {
  display: block;
  margin-bottom: 0;
  color: #334155;
  font-size: 14px;
}

.form-row input,
.form-row select {
  width: 100%;
  height: 38px;
  padding: 0 10px;
  border: 1px solid var(--color-border-strong);
  box-sizing: border-box;
}

.option-group {
  display: grid;
  gap: 6px;
}

.option-group.two {
  grid-template-columns: repeat(2, 1fr);
}

.option-group.three {
  grid-template-columns: repeat(3, 1fr);
}

.option-group.four {
  grid-template-columns: repeat(4, 1fr);
}

.option-group button {
  height: 36px;
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: #334155;
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}

.option-group button:hover {
  background: var(--color-surface-soft);
}

.option-group button.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.primary-button,
.secondary-button {
  width: 100%;
  height: 38px;
  margin-top: 0;
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}

.form-actions {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 10px;
  margin-top: 14px;
}

.form-actions.two {
  grid-template-columns: 64px minmax(0, 1fr) minmax(0, 1fr);
}

.primary-button {
  border: 1px solid var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.primary-button:hover {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

.primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.secondary-button {
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: #334155;
}

.secondary-button:hover {
  background: var(--color-surface-soft);
}

.error-text {
  color: var(--color-danger);
}

.message-text {
  margin: 10px 0 0;
  color: var(--color-muted);
  font-size: 14px;
}

.empty-cell {
  height: 80px;
  text-align: center;
  color: var(--color-muted);
}

@media (max-width: 1280px) {
  .patient-page {
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: 20px;
  }

  .side-panel {
    padding-left: 20px;
  }
}
</style>
