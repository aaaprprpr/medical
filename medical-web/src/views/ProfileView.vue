<script setup>
import { ref } from 'vue'
import { evaluateModelByPath } from '../services/modelEvaluationApi'
import { safeCreateOperationLog } from '../services/operationLogApi'

const dataPath = ref('')
const loading = ref(false)
const errorMessage = ref('')
const resultRows = ref([])
const xlsxBase64 = ref('')
const xlsxFilename = ref('output_table.xlsx')

async function submitEvaluation() {
  const path = dataPath.value.trim()

  if (!path) {
    errorMessage.value = '请填写测试集路径'
    return
  }

  loading.value = true
  errorMessage.value = ''
  resultRows.value = []
  xlsxBase64.value = ''

  try {
    const response = await evaluateModelByPath(path)
    const data = response.data || {}
    resultRows.value = data.results || []
    xlsxBase64.value = data.xlsxBase64 || ''
    xlsxFilename.value = data.xlsxFilename || 'output_table.xlsx'

    await safeCreateOperationLog({
      action: '模型测评',
      detail: `完成 ${resultRows.value.length} 位患者的模型测评`
    })
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

function downloadXlsx() {
  if (!xlsxBase64.value) {
    return
  }

  const binary = atob(xlsxBase64.value)
  const bytes = new Uint8Array(binary.length)

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }

  const blob = new Blob([bytes], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = xlsxFilename.value
  link.click()
  URL.revokeObjectURL(url)
}

function formatScore(value) {
  if (value === null || value === undefined || value === '') {
    return '暂无'
  }

  return Number(value).toFixed(6)
}
</script>

<template>
  <section class="evaluation-page">
    <main class="result-area">
      <div class="result-title">
        <span>共 {{ resultRows.length }} 条</span>
      </div>

      <table class="evaluation-table">
        <thead>
          <tr>
            <th>patient_index</th>
            <th>mace_score</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="row in resultRows" :key="row.patient_index">
            <td>{{ row.patient_index }}</td>
            <td>{{ formatScore(row.mace_score) }}</td>
          </tr>

          <tr v-if="!loading && resultRows.length === 0">
            <td colspan="2" class="empty-cell">暂无测评结果</td>
          </tr>
        </tbody>
      </table>
    </main>

    <aside class="evaluation-panel">
      <h2>模型测评</h2>

      <div class="field-row">
        <span class="field-label">路径</span>
        <input v-model="dataPath" type="text" placeholder="例如：U:\Final_test_data">
      </div>

      <p class="meta-line">后端会直接读取这个路径下的 Cine 和 LGE 文件夹。</p>

      <button class="primary-button" :disabled="loading || !dataPath.trim()" @click="submitEvaluation">
        {{ loading ? '测评中...' : '开始测评' }}
      </button>

      <button class="secondary-button" :disabled="!xlsxBase64" @click="downloadXlsx">
        下载 output_table.xlsx
      </button>

      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    </aside>
  </section>
</template>

<style scoped>
.evaluation-page {
  min-height: calc(100vh - 104px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(320px, 23vw, 380px);
  gap: 30px;
}

.result-area {
  min-width: 0;
  background: var(--color-surface);
}

.result-title {
  min-height: 46px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.result-title h2 {
  margin: 0;
  font-size: 18px;
}

.result-title span {
  color: var(--color-muted);
  font-size: 14px;
}

.evaluation-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-surface);
  font-size: 14px;
}

.evaluation-table th,
.evaluation-table td {
  height: 46px;
  padding: 0 14px;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.evaluation-table th {
  color: #334155;
  font-weight: 600;
  background: var(--color-surface-soft);
}

.evaluation-table tbody tr:hover {
  background: #f8fafc;
}

.evaluation-panel {
  min-width: 0;
  border-left: 1px solid var(--color-border);
  padding-left: 28px;
  padding-right: 8px;
  font-size: 14px;
}

.evaluation-panel h2 {
  margin: 0 0 16px;
  font-size: 18px;
}

.field-row {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.field-label {
  color: #334155;
}

input {
  width: 100%;
  min-width: 0;
  height: 38px;
  padding: 0 10px;
  border: 1px solid var(--color-border-strong);
}

.meta-line {
  margin-top: 8px;
  color: var(--color-muted);
}

.primary-button,
.secondary-button {
  width: 100%;
  height: 38px;
  margin-top: 12px;
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
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

.secondary-button {
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  color: #334155;
}

.secondary-button:hover {
  background: var(--color-surface-soft);
}

.primary-button:disabled,
.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.error-text {
  margin-top: 14px;
  color: var(--color-danger);
}

.empty-cell {
  height: 80px;
  text-align: center;
  color: var(--color-muted);
}

@media (max-width: 1280px) {
  .evaluation-page {
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: 22px;
  }

  .evaluation-panel {
    padding-left: 22px;
  }
}
</style>
