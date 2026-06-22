<script setup>
import { ref, computed } from 'vue'
import { createPatient, createPatientRecord, findPatientByExactName } from '../services/patientApi'
import { safeCreateOperationLog } from '../services/operationLogApi'

const selectedFileName = ref('')
const previewUrl = ref('')
const selectedFile = ref(null)
const result = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const saveMessage = ref('')

const patientName = ref('')
const patientGender = ref('MALE')
const patientAge = ref('')
const isDragging = ref(false)

const cineImages = ref([])
const lgeImages = ref([])
const unmatchedFiles = ref([])

const imageMode = ref('CINE')
const selectedLocation = ref(null)
const isViewerOpen = ref(false)
const viewerIndex = ref(0)


const cineLocations = computed(() => { return [...new Set(cineImages.value.map(image => image.location))] })
const visibleImages = computed(() => {
    if (imageMode.value === 'CINE') {
        return cineImages.value.filter(image => image.location === selectedLocation.value)
    }
    return lgeImages.value
})
const viewerImage = computed(() => {
    return visibleImages.value[viewerIndex.value] ?? null
})


function parsePatientFolder(files) {
    const firstFile = Array.from(files).find(file => file.relativePath || file.webkitRelativePath)
    if (!firstFile) {
        patientName.value = '未找到文件'
    }
    else {
        patientName.value = (firstFile.relativePath || firstFile.webkitRelativePath).split('/')[0]
    }

    const cinePattern = /^([^/]+)\/cine(?:\/sa)?\/location_(\d+)\/frame_(\d+)\.png$/i
    const lgePattern = /^([^/]+)\/lge\/location_(\d+)\.png$/i

    const parsedCine = []
    const parsedLge = []
    const unmatched = []

    for (const file of Array.from(files)) {
        const path = file.relativePath || file.webkitRelativePath || file.name
        const cineMatch = path.match(cinePattern)
        if (cineMatch) {
            parsedCine.push({
                file,
                path,
                url: URL.createObjectURL(file),
                patientName: cineMatch[1],
                location: Number(cineMatch[2]),
                frame: Number(cineMatch[3])
            })
            continue
        }
        const lgeMatch = path.match(lgePattern)
        if (lgeMatch) {
            parsedLge.push({
                file,
                path,
                url: URL.createObjectURL(file),
                patientName: lgeMatch[1],
                location: Number(lgeMatch[2])
            })
            continue
        }
        unmatched.push({ file, path })
    }

    parsedCine.sort((a, b) => a.location - b.location || a.frame - b.frame)
    parsedLge.sort((a, b) => a.location - b.location)
    cineImages.value = parsedCine
    lgeImages.value = parsedLge
    unmatchedFiles.value = unmatched

    imageMode.value = parsedCine.length > 0 ? 'CINE' : 'LGE'
    selectedLocation.value = parsedCine[0]?.location ?? null
    isViewerOpen.value = false
}


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

async function chooseFolder() {
    if (!window.showDirectoryPicker) {
        errorMessage.value = '当前浏览器不支持直接选择文件夹，请使用 Chrome 或 Edge，或者拖拽文件夹'
        return
    }

    try {
        const directoryHandle = await window.showDirectoryPicker()
        const files = []

        await collectDirectoryFiles(directoryHandle, directoryHandle.name, files)
        parsePatientFolder(files)
        useFirstImage(files)
    } catch (error) {
        if (error.name !== 'AbortError') {
            errorMessage.value = error.message
        }
    }
}

async function collectDirectoryFiles(directoryHandle, currentPath, files) {
    for await (const handle of directoryHandle.values()) {
        const childPath = `${currentPath}/${handle.name}`

        if (handle.kind === 'file') {
            const file = await handle.getFile()
            file.relativePath = childPath
            files.push(file)
            continue
        }

        if (handle.kind === 'directory') {
            await collectDirectoryFiles(handle, childPath, files)
        }
    }
}

function switchImageMode(mode) {
    imageMode.value = mode
    isViewerOpen.value = false
    if (mode === 'CINE') {
        selectedLocation.value = cineLocations.value[0] ?? null
    }
}

function openViewer(index) {
    viewerIndex.value = index
    isViewerOpen.value = true
    const image = visibleImages.value[index]
    selectedFile.value = image.file
    selectedFileName.value = image.file.name
    previewUrl.value = image.url
    result.value = null
    errorMessage.value = ''
}
function closeViewer() {
    isViewerOpen.value = false
}
function showPrevImage() {
    if (viewerIndex.value > 0) {
        openViewer(viewerIndex.value - 1)
    }
}
function showNextImage() {
    if (viewerIndex.value < visibleImages.value.length - 1) {
        openViewer(viewerIndex.value + 1)
    }
}


function handleFolderChange(event) {
    parsePatientFolder(event.target.files)
    useFirstImage(event.target.files)
}
function handleDrop(event) {
    isDragging.value = false
    parsePatientFolder(event.dataTransfer.files)
    useFirstImage(event.dataTransfer.files)
}

async function submitPredict() {
    const imagesForPredict = [...cineImages.value, ...lgeImages.value]

    if (imagesForPredict.length === 0) {
        errorMessage.value = '请先选择病人文件夹'
        return
    }

    loading.value = true
    errorMessage.value = ''
    saveMessage.value = ''
    result.value = null
    const formData = new FormData()

    for (const image of imagesForPredict) {
        formData.append('files', image.file, image.path)
    }

    try {
        const patient = await ensurePatientExists()
        const response = await fetch('/api/predict', {
            method: 'POST',
            body: formData
        })
        if (!response.ok) {
            throw new Error(`请求失败: ${response.statusText}`)
        }
        const responseData = await response.json()
        const predictionResult = responseData.data
        result.value = predictionResult
        await saveDetectionRecord(patient, predictionResult)
    } catch (error) {
        errorMessage.value = error.message
    } finally {
        loading.value = false
    }
}

function getPatientGenderLabel() {
    return patientGender.value === 'FEMALE' ? '女' : '男'
}

function getPatientAgeNumber() {
    if (patientAge.value === null || patientAge.value === undefined || String(patientAge.value).trim() === '') {
        throw new Error('未找到已有患者，请填写完整患者信息：年龄不能为空')
    }

    const age = Number(patientAge.value)

    if (!Number.isInteger(age) || age < 0 || age > 120) {
        throw new Error('请填写 0 到 120 之间的整数年龄')
    }

    return age
}

async function ensurePatientExists() {
    const name = patientName.value.trim()

    if (!name) {
        throw new Error('请填写患者姓名')
    }

    const existingPatient = await findPatientByExactName(name)
    if (existingPatient) {
        return existingPatient
    }

    await createPatient({
        name,
        gender: getPatientGenderLabel(),
        age: getPatientAgeNumber()
    })

    const createdPatient = await findPatientByExactName(name)
    if (!createdPatient) {
        throw new Error('患者创建后未找到，请刷新后重试')
    }

    return createdPatient
}

async function saveDetectionRecord(patient, predictionResult) {
    await createPatientRecord(patient.id, {
        result: formatResultLabel(predictionResult.result),
        confidence: predictionResult.probability,
        remark: '影像检测自动保存'
    })

    window.dispatchEvent(new CustomEvent('patient-data-changed'))
    await safeCreateOperationLog({
        action: '影像检测',
        detail: `${patient.name} 完成影像检测，结果：${formatResultLabel(predictionResult.result)}，置信度：${formatProbability(predictionResult.probability)}`
    })
    saveMessage.value = `已保存到 ${patient.name} 的检测记录`
}

function formatResultLabel(resultValue) {
    if (resultValue === 'mace_cine') {
        return '患病'
    }

    if (resultValue === 'no_mace') {
        return '不患病'
    }

    return resultValue || '未知'
}

function formatProbability(value) {
    if (value === null || value === undefined || value === '') {
        return '未知'
    }

    return Number(value).toFixed(4)
}
</script>




<template>
    <section class="test-page">
        <!-- 左面显示图像和列表 -->
        <main class="preview-panel">
            <div class="gallery-layout">
                <!-- 缩略图 -->
                <section class="gallery-main">
                    <div v-if="isViewerOpen && viewerImage" class="viewer">
                        <button class="viewer-close" type="button" @click.stop="closeViewer">×</button>
                        <button class="viewer-arrow viewer-arrow-left" type="button" :disabled="viewerIndex === 0"
                            @click="showPrevImage">
                            &lt;
                        </button>
                        <img :src="viewerImage.url" alt="查看图片">
                        <button class="viewer-arrow viewer-arrow-right" type="button"
                            :disabled="viewerIndex === visibleImages.length - 1" @click="showNextImage">
                            &gt;
                        </button>
                    </div>

                    <div v-else-if="visibleImages.length > 0" class="thumb-grid">
                        <button v-for="(image, index) in visibleImages" :key="image.path" class="thumb" type="button"
                            @click="openViewer(index)">
                            <img :src="image.url" alt="缩略图">
                            <span>
                                {{ imageMode === 'CINE' ? `Frame ${image.frame}` : `Location ${image.location}` }}
                            </span>
                        </button>
                    </div>
                    <p v-else class="empty-text">请先选择文件夹</p>
                </section>

                <aside class="image-nav">

                    <div class="mode-tabs">
                        <button type="button" :class="{ active: imageMode === 'CINE' }"
                            @click="switchImageMode('CINE')">
                            Cine
                        </button>
                        <button type="button" :class="{ active: imageMode === 'LGE' }" @click="switchImageMode('LGE')">
                            LGE
                        </button>
                    </div>


                    <div v-if="imageMode === 'CINE'" class="location-list">
                        <button v-for="location in cineLocations" :key="location" type="button"
                            :class="{ active: selectedLocation === location }"
                            @click="selectedLocation = location; isViewerOpen = false">
                            Location{{ location }}
                        </button>
                    </div>

                </aside>
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
                <p class="hint">拖拽或点击按钮选择文件夹</p>
                <button type="button" class="folder-button" @click="chooseFolder">选择文件夹</button>
            </div>

            <p class="file-name">当前文件夹：{{ patientName || '未选择' }}</p>
            <p>Cine 图片数：{{ cineImages.length }}</p>
            <p>LGE 图片数：{{ lgeImages.length }}</p>

            <button class="predict-button" @click="submitPredict" :disabled="loading || (cineImages.length + lgeImages.length === 0)">
                {{ loading ? '预测中...' : '开始测试' }}
            </button>

            <div v-if="result" class="result">
                <p v-if="saveMessage" class="save-message">{{ saveMessage }}</p>
                <h2>预测结果：</h2>
                <p>判断：{{ formatResultLabel(result.result) }}</p>
                <p>置信度：{{ formatProbability(result.probability) }}</p>
            </div>
            <p v-if="errorMessage" class="error">{{ errorMessage }} </p>

        </aside>
    </section>
</template>


<style scoped>
/* 页面整体布局 */
.test-page {
    display: grid;
    grid-template-columns: minmax(0, 1fr) clamp(320px, 23vw, 380px);
    gap: 30px;
    min-height: calc(100vh - 104px);
}

.preview-panel {
    min-width: 0;
    background: var(--color-surface);
}

.gallery-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 180px;
    gap: 24px;
    min-height: calc(100vh - 112px);
}

.gallery-main {
    min-width: 0;
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
}

/* 本页面按钮基础样式。
   放在具体按钮样式前面，方便后续覆盖。 */
button {
    width: 100%;
    margin-top: 16px;
    padding: 10px 16px;
    border: 1px solid var(--color-border-strong);
    background: var(--color-surface);
    color: #334155;
    cursor: pointer;
    transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
}

button:hover {
    background: var(--color-surface-soft);
}

button:disabled {
    cursor: not-allowed;
    opacity: 0.6;
}

/* 缩略图相册 */
.thumb-grid {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
    gap: 16px;
    align-content: start;
}

.thumb {
    width: 100%;
    margin: 0;
    padding: 6px;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: center;
    transition: background 0.14s ease;
}

.thumb:hover {
    background: var(--color-surface-soft);
}

.thumb img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    display: block;
    border-radius: var(--radius-sm);
}

.thumb span {
    display: block;
    margin-top: 6px;
    font-size: 13px;
    color: var(--color-muted);
}

/* Cine/LGE 图像导航 */
.image-nav {
    border-left: 1px solid var(--color-border);
    padding-left: 16px;
}

.mode-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    margin-bottom: 16px;
}

.mode-tabs button,
.location-list button {
    width: 100%;
    margin: 0;
    padding: 8px 10px;
    border: none;
    background: transparent;
    color: #334155;
    cursor: pointer;
}

.mode-tabs button:hover,
.location-list button:hover {
    background: var(--color-surface-soft);
}

.mode-tabs button.active,
.location-list button.active {
    background: var(--color-primary-soft);
    color: var(--color-primary);
    font-weight: 600;
}

.location-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.nav-hint,
.empty-text {
    color: var(--color-muted);
}

/* 单图查看器 */
.viewer {
    position: relative;
    width: 100%;
    height: calc(100vh - 128px);
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f8fafc;
    overflow: hidden;
}

.viewer img {
    width: min(100%, calc(100vh - 150px));
    height: min(100%, calc(100vh - 150px));
    object-fit: contain;
}

.viewer-close {
    position: absolute;
    top: 18px;
    right: 18px;
    z-index: 3;
    width: 42px;
    height: 42px;
    margin: 0;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: rgba(17, 24, 39, 0.48);
    color: #fff;
    font-size: 22px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.viewer-close:hover {
    background: rgba(17, 24, 39, 0.7);
}

.viewer-arrow {
    position: absolute;
    top: 50%;
    z-index: 2;
    width: 42px;
    height: 42px;
    margin: 0;
    padding: 0;
    transform: translateY(-50%);
    border: none;
    border-radius: 50%;
    background: rgba(17, 24, 39, 0.48);
    color: #fff;
    font-size: 28px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.viewer-arrow:hover {
    background: rgba(17, 24, 39, 0.7);
}

.viewer-arrow:disabled {
    opacity: 0.18;
    cursor: not-allowed;
}

.viewer-arrow-left {
    left: 18px;
}

.viewer-arrow-right {
    right: 18px;
}

/* 右侧控制面板 */
.control-panel {
    min-width: 0;
    border-left: 1px solid var(--color-border);
    padding-left: 28px;
    padding-right: 8px;
}

.control-panel h2 {
    margin: 0 0 16px;
    font-size: 18px;
}

/* 当前保留的级联覆盖 */
.field-row {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr);
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}

.field-label {
    color: #334155;
    font-size: 14px;
}

input {
    width: 100%;
    min-width: 0;
    height: 38px;
    padding: 0 10px;
    border: 1px solid var(--color-border-strong);
}

.segmented {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
}

.segmented button {
    margin: 0;
    padding: 8px 0;
    border: 1px solid var(--color-border-strong);
    background: var(--color-surface);
    cursor: pointer;
}

.segmented button:hover {
    background: var(--color-surface-soft);
}

.segmented button.active {
    color: #fff;
    background: var(--color-primary);
    border-color: var(--color-primary);
}

.drop-zone {
    margin-top: 16px;
    padding: 14px 0 16px;
    background: transparent;
}

.drop-zone.dragging {
    background: var(--color-primary-soft);
}

.hint {
    color: var(--color-muted);
    font-size: 14px;
}

.folder-button {
    margin-top: 8px;
    border: 1px solid var(--color-border-strong);
    background: var(--color-surface);
}

.folder-button:hover {
    background: var(--color-surface-soft);
}

.file-name {
    margin-top: 12px;
}

.error {
    margin-top: 16px;
    color: var(--color-danger);
}

.save-message {
    color: var(--color-success);
}

.result {
    margin-top: 18px;
    padding-top: 12px;
    background: transparent;
    border-top: 1px solid var(--color-border);
}

.predict-button {
    border-color: var(--color-primary);
    background: var(--color-primary);
    color: #fff;
}

.predict-button:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}

@media (max-width: 1280px) {
    .test-page {
        grid-template-columns: minmax(0, 1fr) 320px;
        gap: 22px;
    }

    .gallery-layout {
        grid-template-columns: minmax(0, 1fr) 150px;
        gap: 18px;
    }

    .control-panel {
        padding-left: 22px;
    }
}
</style>
