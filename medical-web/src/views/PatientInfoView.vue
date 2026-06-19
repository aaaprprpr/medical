<script setup>

import { ref } from 'vue'

const patients = ref([
    {
        id: 1,
        name: 'Patient_001',
        gender: '男',
        age: 45,
        latestResult: '患病',
        latestTestTime: '2026-06-17 15:30',
        latestImageName: 'Location_01.png'
    },
    {
        id: 2,
        name: 'Patient_002',
        gender: '女',
        age: 38,
        latestResult: '不患病',
        latestTestTime: '2026-06-16 10:20',
        latestImageName: 'Location_03.png'
    }
])

const searchForm = ref({
    keyword: '',
    gender: '',
    result: ''
})


</script>

<template>
    <section class="patient-page">
        <!-- 表格部分 -->
        <div class="table-area">
            <div class="table-title">
                <span>共 {{ patients.length }} 条</span>
            </div>
            <table class="patient-table">
                <thead>
                    <tr>
                        <th>姓名</th>
                        <th>性别</th>
                        <th>年龄</th>
                        <th>最近检测结果</th>
                        <th>最近检测时间</th>
                        <th>最近图像</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="patient in patients" :key="patient.id">
                        <td>{{ patient.name }}</td>
                        <td>{{ patient.gender }}</td>
                        <td>{{ patient.age }}</td>
                        <td>{{ patient.latestResult }}</td>
                        <td>{{ patient.latestTestTime }}</td>
                        <td>{{ patient.latestImageName }}</td>
                        <td>
                            <button class="text-button">编辑</button>
                            <button class="text-button danger">删除</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <!-- 侧边栏 -->
        <aside class="side-panel">
            <div class="panel-header">
                <h2>筛选面板</h2>
            </div>
            <div class="form-row">
                <label>关键词</label>
                <input v-model="searchForm.keyword" placeholder="姓名 / 图像名">
            </div>
            <div class="form-row">
                <label>性别</label>
                <select v-model="searchForm.gender">
                    <option value="">全部</option>
                    <option value="男">男</option>
                    <option value="女">女</option>
                </select>
            </div>
            <div class="form-row">
                <label>检测结果</label>
                <select v-model="searchForm.result">
                    <option value="">全部</option>
                    <option value="患病">患病</option>
                    <option value="不患病">不患病</option>
                </select>
            </div>
            <button class="primary-button">搜索</button>
            <button class="secondary-button">重置</button>
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

.secondary-button {
  border: 1px solid #d1d5db;
  background: #fff;
  color: #374151;
}
</style>