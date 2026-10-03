import React, { useRef, useEffect } from 'react';
import { Scale, PlusCircle, ShieldAlert } from 'lucide-react';
import { useChatStore } from './store/useChatStore';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { LegalDrawer } from './components/LegalDrawer';

function App() {
  const { messages, isLoading, error, resetChat } = useChatStore();
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex h-screen bg-slate-100 font-sans antialiased text-slate-800">
      {/* Sidebar */}
      <aside className="w-72 bg-slate-900 text-slate-200 flex flex-col border-r border-slate-800">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Scale className="w-6 h-6 text-emerald-400" />
            <h1 className="font-bold text-sm tracking-wide text-white">Qanoon AI</h1>
          </div>
          <button
            onClick={resetChat}
            title="Nouvelle consultation"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <PlusCircle className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 flex-1 overflow-y-auto">
          <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase block mb-3">
            Codes Référencés
          </span>
          <div className="space-y-1.5 text-xs text-slate-300">
            <div className="p-2 rounded bg-slate-800/60 border border-slate-700/50">مدونة الشغل (Travail)</div>
            <div className="p-2 rounded bg-slate-800/60 border border-slate-700/50">قانون المسطرة الجنائية (Proc. Pénale)</div>
            <div className="p-2 rounded bg-slate-800/60 border border-slate-700/50">مدونة الأسرة (Famille)</div>
            <div className="p-2 rounded bg-slate-800/60 border border-slate-700/50">قانون المسطرة المدنية (Proc. Civile)</div>
            <div className="p-2 rounded bg-slate-800/60 border border-slate-700/50">قانون الالتزامات والعقود (D.O.C)</div>
            <div className="p-2 rounded bg-slate-800/60 border border-slate-700/50">مدونة التجارة (Commerce)</div>
          </div>
        </div>

        <div className="p-4 border-t border-slate-800 text-[11px] text-slate-400">
          Système RAG Hybride conforme au droit marocain.
        </div>
      </aside>

      {/* Zone de Chat */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        <div className="flex-1 overflow-y-auto p-6 max-w-4xl w-full mx-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-slate-400 space-y-3">
              <Scale className="w-12 h-12 text-slate-300 stroke-[1.5]" />
              <h2 className="text-lg font-semibold text-slate-700">Consultation Juridique Intelligente</h2>
              <p className="text-sm max-w-md">
                Posez vos questions concernant le droit marocain. Chaque réponse est auditée en temps réel par un AI Judge anti-hallucination.
              </p>
            </div>
          ) : (
            messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)
          )}

          {isLoading && (
            <div className="flex items-center gap-2 text-xs text-slate-500 italic mb-4 animate-pulse">
              <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
              Routage, recherche hybride et audit du Juge en cours...
            </div>
          )}

          {error && (
            <div className="p-4 mb-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2.5">
              <ShieldAlert className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <ChatInput />
      </main>

      {/* Panneau escamotable pour inspecter les textes officiels */}
      <LegalDrawer />
    </div>
  );
}

export default App;