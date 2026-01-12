<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  imageData: { type: Object, default: null }
})

const emit = defineEmits(['close'])
const imageLoading = ref(true)

function handleClose() {
  emit('close')
}

function handleImageLoad() {
  imageLoading.value = false
}

function formatDate(dateInt) {
  if (!dateInt) return '-'
  const str = String(dateInt)
  if (str.length !== 8) return str
  return `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}`
}

const scorePercent = computed(() => {
  if (!props.imageData?.score) return 0
  return (props.imageData.score * 100).toFixed(1)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="handleClose">
      <div class="modal-content">
        <button class="close-btn" @click="handleClose">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>

        <div v-if="imageData" class="detail-container">
          <div class="image-section">
            <div v-if="imageLoading" class="loading-placeholder">
              <div class="loading-spinner"></div>
            </div>
            <img
              :src="imageData.imageUrl || imageData.file_path"
              :alt="imageData.file_name"
              class="full-image"
              @load="handleImageLoad"
            />
          </div>

          <div class="info-section">
            <h3 class="info-title">专利详情</h3>

            <!-- 相似度 -->
            <div class="info-item score-item">
              <span class="info-label">相似度</span>
              <span class="info-value score">{{ scorePercent }}%</span>
              <div class="score-visual">
                <div class="score-fill" :style="{ width: scorePercent + '%' }"></div>
              </div>
            </div>

            <!-- 基本信息 -->
            <div class="info-group">
              <div class="info-item">
                <span class="info-label">专利号</span>
                <span class="info-value">{{ imageData.patent_id }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">设计名称</span>
                <span class="info-value">{{ imageData.title || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">LOC分类</span>
                <span class="info-value">{{ imageData.loc_class || '-' }}</span>
              </div>
            </div>

            <!-- 日期信息 -->
            <div class="info-group">
              <div class="info-item">
                <span class="info-label">公开日期</span>
                <span class="info-value">{{ formatDate(imageData.pub_date) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">申请日期</span>
                <span class="info-value">{{ formatDate(imageData.filing_date) }}</span>
              </div>
            </div>

            <!-- 申请人信息 -->
            <div class="info-group">
              <div class="info-item">
                <span class="info-label">申请人</span>
                <span class="info-value">{{ imageData.applicant_name || '-' }}</span>
              </div>
              <div v-if="imageData.applicant_country" class="info-item">
                <span class="info-label">国家/地区</span>
                <span class="info-value">{{ imageData.applicant_country }}</span>
              </div>
              <div v-if="imageData.inventor_names" class="info-item">
                <span class="info-label">发明人</span>
                <span class="info-value">{{ imageData.inventor_names }}</span>
              </div>
            </div>

            <!-- 权利要求 -->
            <div v-if="imageData.claim_text" class="info-group">
              <div class="info-item">
                <span class="info-label">权利要求</span>
                <span class="info-value claim">{{ imageData.claim_text }}</span>
              </div>
            </div>

            <!-- 图片信息 -->
            <div class="info-group">
              <div class="info-item">
                <span class="info-label">图片序号</span>
                <span class="info-value">{{ (imageData.image_index || 0) + 1 }} / {{ imageData.image_count || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">文件名</span>
                <span class="info-value filename">{{ imageData.file_name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: #fff;
  border-radius: 12px;
  max-width: 1000px;
  max-height: 90vh;
  width: 100%;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: background 0.3s ease;
}

.close-btn:hover {
  background: rgba(0, 0, 0, 0.7);
}

.detail-container {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}

@media (min-width: 768px) {
  .detail-container {
    flex-direction: row;
  }
}

.image-section {
  flex: 1;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  position: relative;
}

.loading-placeholder {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.full-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}

.info-section {
  padding: 24px;
  min-width: 300px;
  max-width: 350px;
  overflow-y: auto;
  max-height: 90vh;
}

.info-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  border-bottom: 2px solid #409eff;
  padding-bottom: 10px;
}

.info-group {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.info-group:last-child {
  border-bottom: none;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-label {
  font-size: 12px;
  color: #909399;
}

.info-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  word-break: break-word;
}

.info-value.filename {
  font-size: 11px;
  font-family: monospace;
  color: #606266;
}

.info-value.claim {
  font-size: 13px;
  font-style: italic;
  color: #606266;
  line-height: 1.5;
}

.score-item {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.info-value.score {
  font-size: 28px;
  color: #409eff;
  font-weight: 600;
}

.score-visual {
  height: 8px;
  background: #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 8px;
}

.score-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  border-radius: 4px;
  transition: width 0.3s ease;
}
</style>
