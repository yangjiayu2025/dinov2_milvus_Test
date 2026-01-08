/**
 * Base 模型 API 模块
 */

const API_BASE = '/api/base'

/**
 * 通用请求封装
 */
async function request(url, options = {}) {
  console.log(`[API-BASE] ${options.method || 'GET'} ${url}`)

  try {
    const response = await fetch(url, options)

    if (!response.ok) {
      const errorText = await response.text()
      console.error(`[API-BASE] Error: ${response.status} ${response.statusText}`, errorText)
      throw new Error(`Request failed: ${response.statusText}`)
    }

    const data = await response.json()
    console.log(`[API-BASE] Response:`, data)
    return data
  } catch (error) {
    console.error(`[API-BASE] Request failed:`, error)
    throw error
  }
}

/**
 * 搜索图片 (Base 模型)
 */
export async function searchImageBase(file, topK = 10, minScore = 0.4) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('top_k', topK)
  formData.append('min_score', minScore)

  return request(`${API_BASE}/search`, {
    method: 'POST',
    body: formData
  })
}

/**
 * 获取 Collection 统计 (Base 模型)
 */
export async function getCollectionStatsBase() {
  return request(`${API_BASE}/collection/stats`)
}

/**
 * 启动批量导入 (Base 模型)
 */
export async function startBatchImportBase() {
  return request(`${API_BASE}/batch/start`, {
    method: 'POST'
  })
}

/**
 * 获取导入状态 (Base 模型)
 */
export async function getBatchStatusBase() {
  return request(`${API_BASE}/batch/status`)
}

/**
 * 重置导入状态 (Base 模型)
 */
export async function resetBatchStatusBase() {
  return request(`${API_BASE}/batch/reset`, {
    method: 'POST'
  })
}

/**
 * 获取缩略图 URL (共用)
 */
export function getThumbnailUrl(fileName) {
  return `/api/image/${fileName}`
}

/**
 * 获取原图 URL (共用)
 */
export function getFullImageUrl(fileName) {
  return `/api/image/full/${fileName}`
}
