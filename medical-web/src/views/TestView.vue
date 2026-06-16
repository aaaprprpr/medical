<script setup>
import { ref } from 'vue'
const selectedFileName = ref('')
const previewUrl = ref('')
const selectedFile = ref(null)
const result = ref(null)
const loading = ref(false)
const errorMessage = ref('')

const patientName = ref('')
const patientGender = ref('MALE')
const patientAge = ref('')
const isDragging = ref(false)


function useFirstImage(files) {
    const imageFiles = Array.from(files).filter(file => file.type.startsWith('image/'))

    if (imageFiles.length === 0) {
        selectedFileName.value = '没找到图片'
        previewUrl.value = ''
        selectedFile.value = null
        result.value = null
        return
    }

    const firstFile = imageFiles[0]

    selectedFileName.value = firstFile.name
    selectedFile.value = firstFile
    previewUrl.value = URL.createObjectURL(firstFile)
    result.value = null
    errorMessage.value = ''
}


function handleFolderChange(event) {
    useFirstImage(event.target.files)
}
function handleDrop(event) {
    isDragging.value = false
    useFirstImage(event.dataTransfer.files)
}
async function submitPredict() {
    if (!selectedFile.value) {
        errorMessage.value = '请先选择图片'
        return
    }

    loading.value = true
    errorMessage.value = ''
    result.value = null
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    try {
        const response = await fetch('/api/mock-predict', {
            method: 'POST',
            body: formData
        })
        if (!response.ok) {
            throw new Error(`请求失败: ${response.statusText}`)
        }
        const responseData = await response.json()
        result.value = responseData.data
    } catch (error) {
        errorMessage.value = error.message
    } finally {
        loading.value = false
    }
}

</script>




<template>
    <!-- 左面显示图像和结果 -->
    <section class="test-page">
        <main class="preview-panel">
            <div class="image-preview">
                <img v-if="previewUrl" :src="previewUrl" alt="预览图片">
                <p v-else>请先选择文件夹</p>
            </div>
        </main>

        <!-- 右面显示控制台按钮啥的 -->
        <aside class="control-panel">
            <h2>控制面板</h2>
            <div class="field-row">
                <span class="field-label">姓名</span>
                <input v-model="patientName" type="text" placeholder="请输入姓名">
            </div>

            <div class="field-row">
                <span class="field-label">性别</span>
                <div class="segmented">
                    <button type="button" :class="{ active: patientGender === 'MALE' }" @click="patientGender = 'MALE'">
                        男
                    </button>
                    <button type="button" :class="{ active: patientGender === 'FEMALE' }"
                        @click="patientGender = 'FEMALE'">
                        女
                    </button>
                </div>
            </div>

            <div class="field-row">
                <span class="field-label">年龄</span>
                <input v-model="patientAge" type="number" min="0" max="120" placeholder="请输入年龄">
            </div>

            <div class="drop-zone" :class="{ dragging: isDragging }" @dragover.prevent="isDragging = true"
                @dragleave.prevent="isDragging = false" @drop.prevent="handleDrop">
                <p class="hint">拖拽或点击按钮上传文件夹</p>
                <input type="file" webkitdirectory multiple @change="handleFolderChange">
            </div>

            <p class="file-name">当前文件夹：{{ selectedFileName || '未选择' }}</p>

            <button @click="submitPredict" :disabled="loading || !selectedFile">
                {{ loading ? '预测中...' : '开始测试' }}
            </button>

            <div v-if="result" class="result">
                <h2>预测结果：</h2>
                <p>判断：{{ result.result }}</p>
                <p>置信度：{{ result.probability }}</p>
                <p>文件名：{{ result.filename }}</p>
            </div>
            <p v-if="errorMessage" class="error">{{ errorMessage }} </p>

        </aside>


    </section>





</template>


<style scoped>
.test-page {
    display: grid;
    grid-template-columns: minmax(0, 1fr) clamp(320px, 22vw, 390px);
    gap: 28px;
    min-height: calc(100vh - 96px);
}

.preview-panel {
    min-width: 0;
}

.preview-panel h1 {
    margin-top: 0;
}

.image-preview {
    min-height: calc(100vh - 112px);
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.image-preview img {
    max-width: 100%;
    max-height: calc(100vh - 128px);
    object-fit: contain;
    display: block;
}

.control-panel {
    min-width: 0;
    border-left: 1px solid #e5e7eb;
    padding-left: 28px;
    padding-right: 8px;
}

.control-panel h2 {
    margin-top: 0;
}

.control-panel {
    min-width: 0;
    border-left: 1px solid #e5e7eb;
    padding-left: 24px;
}

.field-row {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr);
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}

.field-label {
    color: #4b5563;
}

input {
    width: 100%;
    min-width: 0;
    padding: 8px 10px;
    border: 1px solid #d1d5db;
}

.segmented {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
}

.segmented button {
    margin: 0;
    padding: 8px 0;
    border: 1px solid #d1d5db;
    background: #fff;
    cursor: pointer;
}

.segmented button.active {
    color: #fff;
    background: #2563eb;
    border-color: #2563eb;
}

.drop-zone {
    margin-top: 16px;
    padding: 14px 0;
    background: transparent;
}

.drop-zone.dragging {
    background: #f3f4f6;
}

.hint {
    color: #666;
    font-size: 14px;
}

.file-name {
    margin-top: 12px;
}

button {
    width: 100%;
    margin-top: 16px;
    padding: 10px 16px;
    cursor: pointer;
}

button:disabled {
    cursor: not-allowed;
    opacity: 0.6;
}

.error {
    margin-top: 16px;
    color: red;
}

.result {
    margin-top: 18px;
    padding-top: 12px;
    background: transparent;
    border-top: 1px solid #e5e7eb;
}
</style>
