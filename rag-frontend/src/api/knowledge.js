/**
 * 知识库API服务模块
 * 提供知识库和文档的增删改查功能
 */

import { httpClient } from './config.js'

/**
 * 知识库API服务类
 */
class KnowledgeLibraryAPI {
  
  /**
   * 获取用户的知识库列表
   * @returns {Promise} API响应
   */
  async getLibraries() {
    try {
      const response = await httpClient.get('/api/knowledge/libraries')
      return response
    } catch (error) {
      console.error('获取知识库列表失败:', error)
      throw error
    }
  }

  /**
   * 获取知识库详情
   * @param {number} libraryId - 知识库ID
   * @returns {Promise} API响应
   */
  async getLibraryDetail(libraryId) {
    try {
      const response = await httpClient.get(`/api/knowledge/libraries/${libraryId}`)
      return response
    } catch (error) {
      console.error('获取知识库详情失败:', error)
      throw error
    }
  }

  /**
   * 创建知识库
   * @param {Object} libraryData - 知识库数据
   * @param {string} libraryData.title - 知识库标题
   * @param {string} libraryData.description - 知识库描述
   * @returns {Promise} API响应
   */
  async createLibrary(libraryData) {
    try {
      const response = await httpClient.post('/api/knowledge/libraries', libraryData)
      return response
    } catch (error) {
      console.error('创建知识库失败:', error)
      throw error
    }
  }

  /**
   * 更新知识库
   * @param {number} libraryId - 知识库ID
   * @param {Object} libraryData - 知识库数据
   * @returns {Promise} API响应
   */
  async updateLibrary(libraryId, libraryData) {
    try {
      const response = await httpClient.put(`/api/knowledge/libraries/${libraryId}`, libraryData)
      return response
    } catch (error) {
      console.error('更新知识库失败:', error)
      throw error
    }
  }

  /**
   * 删除知识库
   * @param {number} libraryId - 知识库ID
   * @returns {Promise} API响应
   */
  async deleteLibrary(libraryId) {
    try {
      const response = await httpClient.delete(`/api/knowledge/libraries/${libraryId}`)
      return response
    } catch (error) {
      console.error('删除知识库失败:', error)
      throw error
    }
  }

  /**
   * 添加文档到知识库
   * @param {Object} documentData - 文档数据
   * @param {number} documentData.library_id - 知识库ID
   * @param {string} documentData.title - 文档标题
   * @param {string} documentData.content - 文档内容
   * @returns {Promise} API响应
   */
  async addDocument(documentData) {
    try {
      const response = await httpClient.post('/api/knowledge/documents', documentData)
      return response
    } catch (error) {
      console.error('添加文档失败:', error)
      throw error
    }
  }

  /**
   * 更新文档
   * @param {number} documentId - 文档ID
   * @param {Object} documentData - 文档数据
   * @returns {Promise} API响应
   */
  async updateDocument(documentId, documentData) {
    try {
      const response = await httpClient.put(`/api/knowledge/documents/${documentId}`, documentData)
      return response
    } catch (error) {
      console.error('更新文档失败:', error)
      throw error
    }
  }

  /**
   * 删除文档
   * @param {number} documentId - 文档ID
   * @returns {Promise} API响应
   */
  async deleteDocument(documentId) {
    try {
      const response = await httpClient.delete(`/api/knowledge/documents/${documentId}`)
      return response
    } catch (error) {
      console.error('删除文档失败:', error)
      throw error
    }
  }

  /**
   * 获取文件上传URL
   * @param {string} documentName - 文档名称
   * @returns {Promise} API响应
   */
  async getUploadUrl(documentName) {
    try {
      const response = await httpClient.post('/api/knowledge/upload-url', {
        document_name: documentName
      })
      return response
    } catch (error) {
      console.error('获取上传URL失败:', error)
      throw error
    }
  }

  /**
   * 上传文件到OSS
   * @param {string} uploadUrl - 上传URL
   * @param {File} file - 文件对象
   * @returns {Promise} 上传响应
   */
  async uploadFileToOSS(uploadUrl, file) {
    try {
      const formData = new FormData()
      formData.append('file', file)
      
      const response = await fetch(uploadUrl, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type
        }
      })
      
      if (!response.ok) {
        throw new Error(`上传失败: ${response.status} ${response.statusText}`)
      }
      
      return {
        success: true,
        url: uploadUrl.split('?')[0] // 移除查询参数，返回文件URL
      }
    } catch (error) {
      console.error('上传文件到OSS失败:', error)
      throw error
    }
  }

  /**
   * 爬取网站内容
   * @param {Object} crawlData - 爬取数据
   * @param {string} crawlData.url - 网站URL
   * @param {number} crawlData.library_id - 知识库ID
   * @param {number} [crawlData.max_pages] - 最大页面数
   * @returns {Promise} API响应
   */
  async crawlSite(crawlData) {
    try {
      const response = await httpClient.post('/api/crawl/site', crawlData)
      return response
    } catch (error) {
      console.error('爬取网站失败:', error)
      throw error
    }
  }

  /**
   * 本地上传文件并处理（解析 + 切块 + 存储到 Milvus + 可选 LightRAG）
   * @param {File} file - 文件对象
   * @param {string} collectionId - 知识库集合ID
   * @param {number} libraryId - 知识库ID
   * @param {string} chunkStrategy - 切块策略 (markdown/recursive/semantic/character)
   * @returns {Promise} API响应
   */
  async uploadLocalFile(file, collectionId, libraryId, chunkStrategy = 'markdown') {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('collection_id', collectionId)
      formData.append('library_id', libraryId)
      formData.append('chunk_strategy', chunkStrategy)
      
      const response = await httpClient.post('/api/upload/process', formData)
      return response
    } catch (error) {
      console.error('本地上传失败:', error)
      throw error
    }
  }

  /**
   * 获取知识图谱数据
   * @param {string} collectionId - 集合ID
   * @param {string} label - 标签过滤器
   * @returns {Promise} API响应
   */
  async getKnowledgeGraph(collectionId, label = '*') {
    try {
      const response = await httpClient.get(`/api/visual/graph/${collectionId}`, {
        label: label
      })
      return response
    } catch (error) {
      console.error('获取知识图谱失败:', error)
      throw error
    }
  }

  /**
   * 处理 OSS 上传的文档（MinerU 解析 + 切块 + 存储）
   * @param {string} ossUrl - OSS 文件 URL
   * @param {string} collectionId - 知识库集合 ID
   * @param {string} documentName - 文档名称
   * @param {number} libraryId - 知识库 ID
   * @returns {Promise} API响应
   */
  async processOSSDocument(ossUrl, collectionId, documentName, libraryId) {
    try {
      const response = await httpClient.post('/api/crawl/process-oss-document', {
        oss_url: ossUrl,
        collection_id: collectionId,
        document_name: documentName,
        library_id: libraryId
      })
      return response
    } catch (error) {
      console.error('处理 OSS 文档失败:', error)
      throw error
    }
  }
}

// 创建并导出API实例
export const knowledgeAPI = new KnowledgeLibraryAPI()

// 导出默认实例
export default knowledgeAPI