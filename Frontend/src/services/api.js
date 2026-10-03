import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const sendLegalQuery = async (message, threadId = null) => {
  const response = await apiClient.post('/api/chat', {
    message,
    thread_id: threadId,
  });
  return response.data;
};