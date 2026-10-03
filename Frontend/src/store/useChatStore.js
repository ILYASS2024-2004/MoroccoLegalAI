import { create } from 'zustand';
import { sendLegalQuery } from '../services/api';

export const useChatStore = create((set, get) => ({
  messages: [],
  threadId: null,
  isLoading: false,
  error: null,
  selectedDocument: null, // Document affiché dans le panneau latéral

  setThreadId: (id) => set({ threadId: id }),
  setSelectedDocument: (doc) => set({ selectedDocument: doc }),

  resetChat: () =>
    set({
      messages: [],
      threadId: null,
      error: null,
      selectedDocument: null,
    }),

  sendMessage: async (userMessage) => {
    if (!userMessage.trim() || get().isLoading) return;

    const currentThreadId = get().threadId;

    // 1. Ajout immédiat du message utilisateur
    const userMsgObj = {
      id: Date.now().toString(),
      role: 'user',
      content: userMessage,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    set((state) => ({
      messages: [...state.messages, userMsgObj],
      isLoading: true,
      error: null,
    }));

    try {
      // 2. Appel backend FastAPI
      const data = await sendLegalQuery(userMessage, currentThreadId);

      const assistantMsgObj = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer,
        category: data.target_category,
        verificationStatus: data.verification_status,
        citedArticles: data.cited_articles || [],
        contextArticles: data.context_articles || [],
        documents: data.documents || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      set((state) => ({
        messages: [...state.messages, assistantMsgObj],
        threadId: data.thread_id,
        isLoading: false,
      }));
    } catch (err) {
      set({
        error: err.response?.data?.detail || "Erreur de communication avec le serveur d'assistance juridique.",
        isLoading: false,
      });
    }
  },
}));