import React, { useState } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useChatStore } from '../store/useChatStore';

export const ChatInput = () => {
  const [text, setText] = useState('');
  const { sendMessage, isLoading } = useChatStore();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim() || isLoading) return;
    sendMessage(text);
    setText('');
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 bg-white border-t border-slate-200">
      <div className="max-w-4xl mx-auto relative flex items-center">
        <textarea
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          placeholder="Exposez les faits juridiques ou posez votre question (Français, Darija, Arabe)..."
          className="w-full resize-none bg-slate-50 border border-slate-200 rounded-xl pl-4 pr-12 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition"
        />
        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          className="absolute right-2 p-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-lg transition"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </form>
  );
};