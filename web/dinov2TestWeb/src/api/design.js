/**
 * 外观专利 API 模块
 */

const API_BASE = '/api/design'

async function request(url, options = {}) {
  console.log(`[API-DESIGN] ${options.method || 'GET'} ${url}`)

  try {
    const response = await fetch(url, options)

    if (!response.ok) {
      const errorText = await response.text()
      console.error(`[API-DESIGN] Error: ${response.status}`, errorText)
      throw new Error(`Request failed: ${response.statusText}`)
    }

    const data = await response.json()
    console.log(`[API-DESIGN] Response:`, data)
    return data
  } catch (error) {
    console.error(`[API-DESIGN] Request failed:`, error)
    throw error
  }
}

/**
 * 搜索外观专利（支持关键词过滤）
 */
export async function searchDesignPatents(file, options = {}) {
  const { topK = 10, minScore = 0.4, keyword = '', locClass = '', applicant = '' } = options

  const formData = new FormData()
  formData.append('file', file)
  formData.append('top_k', topK)
  formData.append('min_score', minScore)
  if (keyword) formData.append('keyword', keyword)
  if (locClass) formData.append('loc_class', locClass)
  if (applicant) formData.append('applicant', applicant)

  return request(`${API_BASE}/search`, {
    method: 'POST',
    body: formData
  })
}

/**
 * 获取专利详情
 */
export async function getPatentDetail(patentId) {
  return request(`${API_BASE}/patent/${patentId}`)
}

/**
 * 获取 Collection 统计
 */
export async function getDesignStats() {
  return request(`${API_BASE}/stats`)
}

/**
 * 获取外观专利图片 URL（通过后端代理，自动转换格式）
 * @param {string} patentId - 专利号
 * @param {string} fileName - 文件名
 * @param {boolean} thumbnail - 是否获取缩略图
 */
export function getDesignImageUrl(patentId, fileName, thumbnail = true) {
  const params = thumbnail ? '?thumbnail=true' : ''
  return `${API_BASE}/image/${patentId}/${fileName}${params}`
}

/**
 * 从 MinIO URL 中解析专利号和文件名
 * @param {string} minioUrl - MinIO URL，如 http://xxx/design_patents/USD123/file.TIF
 */
export function parseMinioUrl(minioUrl) {
  try {
    // 提取路径部分：design_patents/USD123/file.TIF
    const match = minioUrl.match(/design_patents\/([^\/]+)\/([^\/\?]+)/)
    if (match) {
      return { patentId: match[1], fileName: match[2] }
    }
  } catch (e) {
    console.error('Failed to parse MinIO URL:', minioUrl, e)
  }
  return null
}
