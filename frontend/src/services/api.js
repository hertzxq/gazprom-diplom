import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors (expired token)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ─── Auth ───
export const authApi = {
  login: (username, password) =>
    api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
  register: (data) => api.post('/auth/register', data),
};

// ─── Documents ───
export const documentsApi = {
  upload: (file, fileType, metadata = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_type', fileType);
    formData.append('metadata', JSON.stringify(metadata));
    return api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  list: (params = {}) => api.get('/documents/', { params }),
  get: (id) => api.get(`/documents/${id}`),
  download: (id) =>
    api.get(`/documents/${id}/download`, { responseType: 'blob' }),
  process: (data) => api.post('/documents/process', data),
};

// ─── Manufacturers ───
export const manufacturersApi = {
  searchBySpecs: (data) => api.post('/manufacturers/search-by-specs', data),
  searchByName: (data) => api.post('/manufacturers/search-by-name', data),
  export: (data) =>
    api.post('/manufacturers/export', data, { responseType: 'blob' }),
};

// ─── Notifications ───
export const notificationsApi = {
  list: (params = {}) => api.get('/notifications/', { params }),
  markRead: (id) => api.patch(`/notifications/${id}/read`),
  markAllRead: () => api.patch('/notifications/read-all'),
};

// ─── Admin ───
export const adminApi = {
  listUsers: () => api.get('/admin/users'),
  updateUser: (id, data) => api.patch(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
};

// ─── Analytics ───
export const analyticsApi = {
  getSummary: () => api.get('/analytics/summary'),
};

// ─── Task 2: первичный свод / итоговый свод СМСП ───
export const task2Api = {
  buildPrimarySumup: (data) => api.post('/documents/task2/primary-sumup', data),
  updatePrimarySumup: (taskId, data) =>
    api.put(`/documents/task2/primary-sumup/${taskId}`, data),
  buildFinalSummary: (data) => api.post('/documents/task2/final-summary', data),
  listExclusionRules: () => api.get('/documents/task2/exclusion-rules'),
  updateExclusionRules: (rules) =>
    api.put('/documents/task2/exclusion-rules', { rules }),
};

export default api;

