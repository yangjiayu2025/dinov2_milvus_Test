<script setup>
import { ref, onMounted } from 'vue'
import ImageUploader from '../components/ImageUploader.vue'
import TimingPanel from '../components/TimingPanel.vue'
import SearchResults from '../components/SearchResults.vue'
import BatchImportPanelBase from '../components/BatchImportPanelBase.vue'
import ImageDetailModal from '../components/ImageDetailModal.vue'
import { searchImageBase, getCollectionStatsBase } from '../api/base'

// 状态
const loading = ref(false)
const results = ref([])
const timing = ref({})
const queryInfo = ref({})
const collectionStats = ref(null)
const error = ref(null)

// 弹窗状态
const modalVisible = ref(false)
const selectedImage = ref(null)

// 搜索参数
const topK = ref(10)
const minScore = ref(0.4)

// 获取统计信息
async function fetchStats() {
  try {
    const res = await getCollectionStatsBase()
    collectionStats.value = res.data
  } catch (e) {
    console.error('Failed to fetch stats:', e)
  }
}

// 处理上传搜索
async function handleUpload(file) {
  loading.value = true
  error.value = null

  try {
    const res = await searchImageBase(file, topK.value, minScore.value)

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
function handleViewDetail(data) {
  selectedImage.value = data
  modalVisible.value = true
}

// 关闭弹窗
function handleCloseModal() {
  modalVisible.value = false
  selectedImage.value = null
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
          <h1 class="title">DINOv2 图像检索系统</h1>
          <span class="model-badge base">Base 模型 (768维)</span>
        </div>
        <div class="header-right">
          <router-link to="/" class="switch-btn">切换到 Small 模型</router-link>
          <div v-if="collectionStats" class="db-status">
            <span class="status-dot"></span>
            <span>数据库: {{ collectionStats.collection?.num_entities || 0 }} 张图片</span>
          </div>
        </div>
      </div>
    </header>

    <!-- 提示条 -->
    <div class="info-banner">
      当前使用 <strong>DINOv2 Base 模型</strong>，向量维度 768 维，相比 Small 模型 (384维) 特征表达能力更强，但推理速度稍慢。
    </div>

    <main class="main">
      <div class="container">
        <!-- 上传区域 -->
        <section class="upload-section">
          <ImageUploader @upload="handleUpload" />
        </section>

        <!-- 中间区域：查询预览 + 性能面板 -->
        <section class="middle-section">
          <div class="timing-wrapper">
            <TimingPanel :timing="timing" />
          </div>
          <div class="import-wrapper">
            <BatchImportPanelBase />
          </div>
        </section>

        <!-- 错误提示 -->
        <div v-if="error" class="error-alert">
          <span>{{ error }}</span>
          <button @click="error = null">关闭</button>
        </div>

        <!-- 搜索结果 -->
        <section class="results-section">
          <SearchResults
            :results="results"
            :query-info="queryInfo"
            :loading="loading"
            @view-detail="handleViewDetail"
          />
        </section>
      </div>
    </main>

    <!-- 详情弹窗 -->
    <ImageDetailModal
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
}

.model-badge.base {
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.switch-btn {
  padding: 6px 14px;
  background: #67c23a;
  color: #fff;
  border-radius: 4px;
  text-decoration: none;
  font-size: 14px;
  transition: background 0.2s;
}

.switch-btn:hover {
  background: #85ce61;
}

.info-banner {
  background: linear-gradient(90deg, #f6ffed 0%, #e6fffb 100%);
  border-bottom: 1px solid #b7eb8f;
  padding: 12px 24px;
  text-align: center;
  font-size: 14px;
  color: #52c41a;
}

.info-banner strong {
  color: #389e0d;
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

.middle-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .middle-section {
    grid-template-columns: 1fr;
  }
}

.timing-wrapper,
.import-wrapper {
  min-width: 0;
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

.error-alert button {
  background: none;
  border: none;
  color: #f56c6c;
  cursor: pointer;
  font-size: 12px;
}

.results-section {
  margin-bottom: 24px;
}
</style>
