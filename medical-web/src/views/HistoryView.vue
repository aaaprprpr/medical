<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { clearOperationLogs, deleteOperationLog, listOperationLogs } from '../services/operationLogApi'

const logs = ref([])
const loading = ref(false)
const deletingId = ref(null)
const clearing = ref(false)
const errorMessage = ref('')

async function loadLogs() {
  loading.value = true
  errorMessage.value = ''

  try {
    const response = await listOperationLogs()
    logs.value = response.data || []
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function handleDeleteLog(log) {
  deletingId.value = log.id
  errorMessage.value = ''

  try {
    await deleteOperationLog(log.id)
    await loadLogs()
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    deletingId.value = null
  }
}

async function handleClearLogs() {
  if (logs.value.length === 0) {
    return
  }

  const confirmed = window.confirm('确认清空全部操作记录吗？')
  if (!confirmed) {
    return
  }

  clearing.value = true
  errorMessage.value = ''

  try {
    await clearOperationLogs()
    logs.value = []
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    clearing.value = false
  }
}

function formatTime(value) {
  if (!value) {
    return '暂无'
  }

  return value.replace('T', ' ').slice(0, 19)
}

function handleOperationLogChanged() {
  loadLogs()
}

onMounted(() => {
  loadLogs()
  window.addEventListener('operation-log-changed', handleOperationLogChanged)
})

onBeforeUnmount(() => {
  window.removeEventListener('operation-log-changed', handleOperationLogChanged)
})
</script>

<template>
  <section class="log-page">
    <div class="log-toolbar">
      <div>
        <h2>操作记录</h2>
        <p>共 {{ logs.length }} 条记录</p>
      </div>

      <div class="toolbar-actions">
        <button type="button" class="secondary-button" :disabled="loading" @click="loadLogs">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <button type="button" class="danger-button" :disabled="clearing || logs.length === 0" @click="handleClearLogs">
          {{ clearing ? '清空中...' : '一键清空' }}
        </button>
      </div>
    </div>

    <div class="status-line">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </div>

    <table class="log-table">
      <thead>
        <tr>
          <th>操作</th>
          <th>内容</th>
          <th>时间</th>
          <th>处理</th>
        </tr>
      </thead>

      <tbody>
        <tr v-for="log in logs" :key="log.id">
          <td>{{ log.action }}</td>
          <td>{{ log.detail || '无详情' }}</td>
          <td>{{ formatTime(log.createdAt) }}</td>
          <td>
            <button type="button" class="text-danger-button" :disabled="deletingId === log.id"
              @click="handleDeleteLog(log)">
              {{ deletingId === log.id ? '删除中...' : '删除' }}
            </button>
          </td>
        </tr>

        <tr v-if="!loading && logs.length === 0">
          <td colspan="4" class="empty-cell">暂无操作记录</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<style scoped>
.log-page {
  min-height: calc(100vh - 104px);
  background: var(--color-surface);
}

.log-toolbar {
  min-height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
}

.log-toolbar h2 {
  margin: 0;
  font-size: 22px;
}

.log-toolbar p {
  margin: 6px 0 0;
  color: var(--color-muted);
  font-size: 14px;
}

.toolbar-actions {
  display: flex;
  gap: 10px;
}

.secondary-button,
.danger-button {
  height: 38px;
  min-width: 92px;
  padding: 0 14px;
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}

.secondary-button {
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: #334155;
}

.secondary-button:hover {
  background: var(--color-surface-soft);
}

.danger-button {
  border: 1px solid var(--color-danger);
  background: var(--color-danger);
  color: #fff;
}

.danger-button:hover {
  background: #b91c1c;
  border-color: #b91c1c;
}

.secondary-button:disabled,
.danger-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.status-line {
  min-height: 32px;
  display: flex;
  align-items: center;
}

.error-text {
  color: var(--color-danger);
}

.log-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-surface);
}

.log-table th,
.log-table td {
  height: 44px;
  padding: 0 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.log-table th {
  color: #334155;
  font-weight: 600;
  background: var(--color-surface-soft);
}

.log-table td {
  color: var(--color-text);
}

.log-table tbody tr {
  transition: background 0.14s ease;
}

.log-table tbody tr:hover {
  background: #f8fafc;
}

.log-table th:nth-child(2),
.log-table td:nth-child(2) {
  width: 100%;
  white-space: normal;
}

.log-table th:nth-child(3),
.log-table td:nth-child(3) {
  width: 180px;
}

.log-table th:nth-child(4),
.log-table td:nth-child(4) {
  width: 80px;
  text-align: right;
}

.text-danger-button {
  padding: 4px 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-danger);
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease;
}

.text-danger-button:hover {
  border-color: #fecaca;
  background: var(--color-danger-soft);
}

.text-danger-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.empty-cell {
  height: 80px;
  text-align: center;
  color: var(--color-muted);
}
</style>
