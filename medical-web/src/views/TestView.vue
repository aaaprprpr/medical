<script setup>
import { ref, computed } from 'vue'

// 预测请求状态
const selectedFileName = ref('')
const previewUrl = ref('')
const selectedFile = ref(null)
const result = ref(null)
const loading = ref(false)
const errorMessage = ref('')

// 患者表单状态
const patientName = ref('')
const patientGender = ref('MALE')
const patientAge = ref('')
const isDragging = ref(false)

// 解析后的患者文件夹图像数据
const cineImages = ref([])
const lgeImages = ref([])
const unmatchedFiles = ref([])

// 图像相册和查看器状态
const imageMode = ref('CINE')
const selectedLocation = ref(null)
const isViewerOpen = ref(false)
const viewerIndex = ref(0)


// 相册派生数据
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


// 将选中的患者文件夹解析成 Cine/LGE 图像列表
function parsePatientFolder(files) {
    const firstFile = Array.from(files).find(file => file.webkitRelativePath)
    if (!firstFile) {
        patientName.value = '未找到文件'
    }
    else {
        patientName.value = firstFile.webkitRelativePath.split('/')[0]
    }

    const cinePattern = /^([^/]+)\/cine(?:\/sa)?\/location_(\d+)\/frame_(\d+)\.png$/i
    const lgePattern = /^([^/]+)\/lge\/location_(\d+)\.png$/i

    const parsedCine = []
    const parsedLge = []
    const unmatched = []

    for (const file of Array.from(files)) {
        const path = file.webkitRelativePath || file.name
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


// 保留第一张图像，给当前后端预测流程使用
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

// 切换 Cine/LGE 相册模式
function switchImageMode(mode) {
    imageMode.value = mode
    isViewerOpen.value = false
    if (mode === 'CINE') {
        selectedLocation.value = cineLocations.value[0] ?? null
    }
}

// 单图查看器控制
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


// 文件夹选择和拖拽处理
function handleFolderChange(event) {
    parsePatientFolder(event.target.files)
    useFirstImage(event.target.files)
}
function handleDrop(event) {
    isDragging.value = false
    parsePatientFolder(event.dataTransfer.files)
    useFirstImage(event.dataTransfer.files)
}

// 后端预测请求
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

                <!-- 区域列表 -->
                <aside class="image-nav">
                    <!-- 切换按钮 -->
                    <div class="mode-tabs">
                        <button type="button" :class="{ active: imageMode === 'CINE' }"
                            @click="switchImageMode('CINE')">
                            Cine
                        </button>
                        <button type="button" :class="{ active: imageMode === 'LGE' }" @click="switchImageMode('LGE')">
                            LGE
                        </button>
                    </div>

                    <!-- 列表 -->
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
                <p class="hint">拖拽或点击按钮上传文件夹</p>
                <input type="file" webkitdirectory multiple @change="handleFolderChange">
            </div>

            <p class="file-name">当前文件夹：{{ patientName || '未选择' }}</p>
            <p>Cine 图片数：{{ cineImages.length }}</p>
            <p>LGE 图片数：{{ lgeImages.length }}</p>
            <!-- <p>未匹配文件数：{{ unmatchedFiles.length }}</p> -->

            <button @click="submitPredict" :disabled="loading || !selectedFile">
                {{ loading ? '预测中...' : '开始测试' }}
            </button>

            <div v-if="result" class="result">
                <h2>预测结果：</h2>
                <p>判断：{{ result.result }}</p>
                <p>置信度：{{ result.probability }}</p>
            </div>
            <p v-if="errorMessage" class="error">{{ errorMessage }} </p>

        </aside>
    </section>
</template>


<style scoped>
/* 页面整体布局 */
.test-page {
    display: grid;
    grid-template-columns: minmax(0, 1fr) clamp(320px, 22vw, 390px);
    gap: 28px;
    min-height: calc(100vh - 96px);
}

.preview-panel {
    min-width: 0;
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
    cursor: pointer;
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
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    text-align: center;
}

.thumb img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    display: block;
}

.thumb span {
    display: block;
    margin-top: 6px;
    font-size: 13px;
    color: #6b7280;
}

/* Cine/LGE 图像导航 */
.image-nav {
    border-left: 1px solid #e5e7eb;
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
    cursor: pointer;
}

.mode-tabs button.active,
.location-list button.active {
    background: #eff6ff;
    color: #2563eb;
}

.location-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.nav-hint,
.empty-text {
    color: #6b7280;
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
    border-left: 1px solid #e5e7eb;
    padding-left: 28px;
    padding-right: 8px;
}

.control-panel h2 {
    margin-top: 0;
}

/* 当前保留的级联覆盖 */
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
