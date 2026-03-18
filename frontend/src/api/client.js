import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 60000 })

export const uploadFile = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/ingest/file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => onProgress?.(Math.round(e.loaded * 100 / e.total))
  })
}
export const ingestUrl = url => api.post('/ingest/url', { url })
export const getDocuments = () => api.get('/documents')
export const deleteDocument = id => api.delete(`/documents/${id}`)
export const getChunks = (docId, offset = 0, limit = 50) =>
  api.get('/chunks', { params: { doc_id: docId, offset, limit } })
export const getStats = () => api.get('/stats')

export const chatOnce = (query, sessionId, docIds) =>
  api.post('/chat', { query, session_id: sessionId, doc_ids: docIds })
export const getSessions = () => api.get('/sessions')
export const createSession = () => api.post('/sessions')
export const deleteSession = id => api.delete(`/sessions/${id}`)
export const getMessages = id => api.get(`/sessions/${id}/messages`)

export const generateQuiz = (docIds, quizType, nQuestions) =>
  api.post('/quiz/generate', { doc_ids: docIds, quiz_type: quizType, n_questions: nQuestions })
export const getQuizzes = () => api.get('/quiz')
export const getQuiz = id => api.get(`/quiz/${id}`)
export const deleteQuiz = id => api.delete(`/quiz/${id}`)

export default api
