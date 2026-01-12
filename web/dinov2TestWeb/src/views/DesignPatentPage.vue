<script setup>
import { ref, onMounted } from 'vue'
import ImageUploader from '../components/ImageUploader.vue'
import TimingPanel from '../components/TimingPanel.vue'
import PatentDetailModal from '../components/PatentDetailModal.vue'
import { searchDesignPatents, getDesignStats, getDesignImageUrl, parseMinioUrl } from '../api/design'

// 状态
const loading = ref(false)
const results = ref([])
const timing = ref({})
const queryInfo = ref({})
const collectionStats = ref(null)
const error = ref(null)
const selectedFile = ref(null)  // 保存选中的文件

// 弹窗状态
const modalVisible = ref(false)
const selectedImage = ref(null)

// 搜索参数
const topK = ref(10)
const minScore = ref(0.4)
const keyword = ref('')
const locClass = ref('')
const applicant = ref('')

// 获取统计信息
async function fetchStats() {
  try {
    const res = await getDesignStats()
    collectionStats.value = res.data
  } catch (e) {
    console.error('Failed to fetch stats:', e)
  }
}

// 处理上传（只保存文件，不自动搜索）
function handleUpload(file) {
  selectedFile.value = file
}

// 执行搜索
async function doSearch() {
  if (!selectedFile.value) {
    error.value = '请先上传图片'
    return
  }

  loading.value = true
  error.value = null

  try {
    const res = await searchDesignPatents(selectedFile.value, {
      topK: topK.value,
      minScore: minScore.value,
      keyword: keyword.value || undefined,
      locClass: locClass.value || undefined,
      applicant: applicant.value || undefined
    })

    if (res.code === 0) {
      results.value = res.data.results
      timing.value = res.data.timing
      queryInfo.value = res.data.query_info
    } else {
      error.value = res.message
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// 查看详情
function handleViewDetail(patent, page) {
  selectedImage.value = {
    ...page,
    // 添加转换后的图片 URL（原图）
    imageUrl: getImageUrl(page, false),
    patent_id: patent.patent_id,
    title: patent.title,
    loc_class: patent.loc_class,
    pub_date: patent.pub_date,
    filing_date: patent.filing_date,
    applicant_name: patent.applicant_name,
    applicant_country: patent.applicant_country,
    inventor_names: patent.inventor_names,
    claim_text: patent.claim_text,
    image_count: patent.image_count
  }
  modalVisible.value = true
}

// 关闭弹窗
function handleCloseModal() {
  modalVisible.value = false
  selectedImage.value = null
}

// 格式化日期
function formatDate(dateInt) {
  if (!dateInt) return '-'
  const str = String(dateInt)
  if (str.length !== 8) return str
  return `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}`
}

// 获取图片显示 URL（通过代理转换格式）
function getImageUrl(page, thumbnail = true) {
  // 从 MinIO URL 解析专利号和文件名
  const parsed = parseMinioUrl(page.file_path)
  if (parsed) {
    return getDesignImageUrl(parsed.patentId, parsed.fileName, thumbnail)
  }
  // 如果解析失败，直接使用原始 URL（可能无法显示）
  return page.file_path
}

onMounted(() => {
  fetchStats()
})
</script>

<template>
  <div class="page">
    <header class="header">
      <div class="header-content">
        <div class="header-left">
          <h1 class="title">外观专利图像检索</h1>
          <span class="model-badge">DINOv2 Base</span>
        </div>
        <div class="header-right">
          <router-link to="/base" class="switch-btn">返回通用检索</router-link>
          <div v-if="collectionStats" class="db-status">
            <span class="status-dot"></span>
            <span>专利库: {{ collectionStats.collection?.num_entities || 0 }} 张图片</span>
          </div>
        </div>
      </div>
    </header>

    <main class="main">
      <div class="container">
        <!-- 上传区域 -->
        <section class="upload-section">
          <ImageUploader @upload="handleUpload" />
        </section>

        <!-- 过滤条件 -->
        <section class="filter-section">
          <h3 class="filter-title">搜索条件（可选）</h3>
          <div class="filter-grid">
            <div class="filter-item">
              <label>关键词 (标题)</label>
              <input v-model="keyword" type="text" placeholder="如: Shoe, Watch" />
            </div>
            <div class="filter-item">
              <label>LOC 分类</label>
              <input v-model="locClass" type="text" placeholder="如: 0204" />
            </div>
            <div class="filter-item">
              <label>申请人</label>
              <input v-model="applicant" type="text" placeholder="如: Nike" />
            </div>
            <div class="filter-item">
              <label>最低相似度</label>
              <input v-model.number="minScore" type="number" min="0" max="1" step="0.1" />
            </div>
          </div>
          <div class="search-actions">
            <button
              class="search-btn"
              :class="{ disabled: !selectedFile }"
              :disabled="!selectedFile || loading"
              @click="doSearch"
            >
              <span v-if="loading">搜索中...</span>
              <span v-else>开始搜索</span>
            </button>
            <span v-if="!selectedFile" class="search-hint">请先上传图片</span>
            <span v-else class="search-hint ready">图片已就绪，可以搜索</span>
          </div>
        </section>

        <!-- 性能面板 -->
        <section class="timing-section">
          <TimingPanel :timing="timing" />
        </section>

        <!-- 错误提示 -->
        <div v-if="error" class="error-alert">
          <span>{{ error }}</span>
          <button @click="error = null">关闭</button>
        </div>

        <!-- 搜索结果 -->
        <section class="results-section">
          <div v-if="loading" class="loading">
            <div class="spinner"></div>
            <span>搜索中...</span>
          </div>

          <div v-else-if="results.length === 0" class="empty">
            <p>上传图片开始搜索</p>
          </div>

          <div v-else class="results-list">
            <h3 class="results-title">
              搜索结果 ({{ results.length }} 个专利)
              <span v-if="queryInfo.keyword" class="filter-tag">关键词: {{ queryInfo.keyword }}</span>
              <span v-if="queryInfo.loc_class" class="filter-tag">LOC: {{ queryInfo.loc_class }}</span>
            </h3>

            <div v-for="patent in results" :key="patent.patent_id" class="patent-card">
              <div class="patent-header">
                <div class="patent-info">
                  <span class="patent-id">{{ patent.patent_id }}</span>
                  <span class="patent-title">{{ patent.title }}</span>
                  <span class="patent-score">{{ (patent.max_score * 100).toFixed(1) }}%</span>
                </div>
                <div class="patent-meta">
                  <span v-if="patent.loc_class" class="meta-item">LOC: {{ patent.loc_class }}</span>
                  <span v-if="patent.applicant_name" class="meta-item">{{ patent.applicant_name }}</span>
                  <span v-if="patent.pub_date" class="meta-item">{{ formatDate(patent.pub_date) }}</span>
                </div>
              </div>

              <div class="patent-images">
                <div
                  v-for="page in patent.pages"
                  :key="page.id"
                  class="image-item"
                  @click="handleViewDetail(patent, page)"
                >
                  <img :src="getImageUrl(page, true)" :alt="page.file_name" />
                  <div class="image-score">{{ (page.score * 100).toFixed(0) }}%</div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>

    <!-- 详情弹窗 -->
    <PatentDetailModal
      :visible="modalVisible"
      :image-data="selectedImage"
      @close="handleCloseModal"
    />
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.header {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  padding: 16px 24px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.model-badge {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  background: #ecf5ff;
  color: #409eff;
  border: 1px solid #b3d8ff;
}

.switch-btn {
  padding: 6px 14px;
  background: #409eff;
  color: #fff;
  border-radius: 4px;
  text-decoration: none;
  font-size: 14px;
}

.db-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #606266;
}

.status-dot {
  width: 8px;
  height: 8px;
  background: #67c23a;
  border-radius: 50%;
}

.main {
  flex: 1;
  padding: 24px;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
}

.upload-section {
  margin-bottom: 24px;
}

.filter-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.filter-title {
  margin: 0 0 16px 0;
  font-size: 14px;
  color: #606266;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-item label {
  font-size: 12px;
  color: #909399;
}

.filter-item input {
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 14px;
}

.filter-item input:focus {
  outline: none;
  border-color: #409eff;
}

.search-actions {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.search-btn {
  padding: 12px 32px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.search-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.search-btn:disabled,
.search-btn.disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.search-hint {
  font-size: 13px;
  color: #909399;
}

.search-hint.ready {
  color: #67c23a;
}

.timing-section {
  margin-bottom: 24px;
}

.error-alert {
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #f56c6c;
}

.loading {
  text-align: center;
  padding: 60px;
  color: #909399;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #ebeef5;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty {
  text-align: center;
  padding: 60px;
  color: #909399;
}

.results-title {
  margin: 0 0 20px 0;
  font-size: 16px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-tag {
  font-size: 12px;
  padding: 2px 8px;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 4px;
  font-weight: normal;
}

.patent-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.patent-header {
  margin-bottom: 16px;
}

.patent-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.patent-id {
  font-weight: 600;
  color: #303133;
}

.patent-title {
  color: #606266;
}

.patent-score {
  margin-left: auto;
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
}

.patent-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
}

.patent-images {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.image-item {
  flex-shrink: 0;
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}

.image-item:hover {
  border-color: #409eff;
}

.image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-score {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
