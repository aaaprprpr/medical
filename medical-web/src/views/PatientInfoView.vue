<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { createPatient, deletePatient, listPatients, updatePatient } from '../services/patientApi'

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
              <span class="header-cell">
                姓名
                <button class="sort-button" title="点击排序" @click="changeSort('name')">
                  {{ getSortIcon('name') }}
                </button>
              </span>
            </th>
            <th>
              <span class="header-cell">
                性别
                <button class="sort-button" title="点击排序" @click="changeSort('gender')">
                  {{ getSortIcon('gender') }}
                </button>
              </span>
            </th>
            <th>
              <span class="header-cell">
                年龄
                <button class="sort-button" title="点击排序" @click="changeSort('age')">
                  {{ getSortIcon('age') }}
                </button>
              </span>
            </th>
            <th>
              <span class="header-cell">
                最近检测结果
                <button class="sort-button" title="点击排序" @click="changeSort('latestResult')">
                  {{ getSortIcon('latestResult') }}
                </button>
              </span>
            </th>
            <th>
              <span class="header-cell">
                置信度
                <button class="sort-button" title="点击排序" @click="changeSort('latestConfidence')">
                  {{ getSortIcon('latestConfidence') }}
                </button>
              </span>
            </th>
            <th>
              <span class="header-cell">
                最近检测时间
                <button class="sort-button" title="点击排序" @click="changeSort('latestTestedAt')">
                  {{ getSortIcon('latestTestedAt') }}
                </button>
              </span>
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

        <button class="primary-button" :disabled="submitting" @click="handleCreatePatient">
          {{ submitting ? '添加中...' : '添加患者' }}
        </button>
        <p v-if="createMessage" class="message-text">{{ createMessage }}</p>
      </section>

      <section class="panel-section">
        <div class="panel-header">
          <h2>筛选面板</h2>
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

        <button class="primary-button" @click="handleSearch">搜索</button>
        <button class="secondary-button" @click="resetSearch">重置</button>
      </section>
    </aside>
  </section>
</template>

<style scoped>
.patient-page {
  min-height: calc(100vh - 96px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 20px;
}

.table-area {
  min-width: 0;
  background: #fff;
}

.table-title {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-title h2 {
  margin: 0;
  font-size: 20px;
}

.table-title span {
  color: #6b7280;
  font-size: 14px;
}

.patient-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}

.patient-table th,
.patient-table td {
  height: 44px;
  padding: 0 12px;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
}

.patient-table th {
  color: #374151;
  font-weight: 600;
  background: #f9fafb;
}

.patient-table td {
  color: #111827;
}

.table-edit-input {
  width: 100%;
  height: 30px;
  padding: 0 8px;
  border: 1px solid #d1d5db;
  box-sizing: border-box;
}

.header-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.sort-button {
  width: 22px;
  height: 22px;
  border: 1px solid transparent;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  line-height: 1;
}

.sort-button:hover {
  border-color: #d1d5db;
  background: #f3f4f6;
  color: #111827;
}

.text-button {
  margin-right: 8px;
  border: none;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
}

.text-button.danger {
  color: #dc2626;
}

.side-panel {
  padding-left: 24px;
  border-left: 1px solid #e5e7eb;
}

.panel-section + .panel-section {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid #e5e7eb;
}

.panel-header h2 {
  margin: 0 0 20px;
  font-size: 22px;
}

.form-row {
  margin-bottom: 16px;
}

.form-row label {
  display: block;
  margin-bottom: 6px;
  color: #374151;
}

.form-row input,
.form-row select {
  width: 100%;
  height: 36px;
  padding: 0 10px;
  border: 1px solid #d1d5db;
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
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
  cursor: pointer;
}

.option-group button:hover {
  background: #f3f4f6;
}

.option-group button.active {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.primary-button,
.secondary-button {
  width: 100%;
  height: 38px;
  margin-top: 8px;
  cursor: pointer;
}

.primary-button {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: #fff;
}

.primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.secondary-button {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
}

.error-text {
  color: #dc2626;
}

.message-text {
  margin: 10px 0 0;
  color: #4b5563;
  font-size: 14px;
}

.empty-cell {
  height: 80px;
  text-align: center;
  color: #6b7280;
}
</style>
