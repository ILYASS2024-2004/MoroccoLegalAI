import React from 'react';
import { ShieldCheck, AlertTriangle, BookMarked, User, Bot } from 'lucide-react';
import { useChatStore } from '../store/useChatStore';

export const ChatMessage = ({ message }) => {
  const isUser = message.role === 'user';
  const setSelectedDocument = useChatStore((state) => state.setSelectedDocument);

  if (isUser) {
    return (
      <div className="flex justify-end gap-3 mb-6">
        <div className="max-w-[75%] bg-slate-900 text-white rounded-2xl rounded-tr-sm px-5 py-3.5 shadow-sm">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          <span className="block text-[10px] text-slate-400 text-right mt-1.5">{message.timestamp}</span>
        </div>
        <div className="w-8 h-8 rounded-full bg-slate-800 text-slate-200 flex items-center justify-center flex-shrink-0 text-xs font-semibold">
          <User className="w-4 h-4" />
        </div>
      </div>
    );
  }

  const isVerified = message.verificationStatus === 'pass';

  return (
    <div className="flex gap-3 mb-6">
      <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center flex-shrink-0 text-xs font-semibold shadow-sm">
        <Bot className="w-4 h-4" />
      </div>

      <div className="max-w-[85%] space-y-3">
        <div className="bg-white border border-slate-200/80 rounded-2xl rounded-tl-sm p-5 shadow-sm space-y-3">
          {/* Badge de conformité AI Judge */}
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Code ciblé : <strong className="text-slate-800">{message.category || 'Général'}</strong>
            </span>

            {isVerified ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5" />
                Audité & Conforme
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                <AlertTriangle className="w-3.5 h-3.5" />
                Réserve Juridique
              </span>
            )}
          </div>

          {/* Synthèse juridique */}
          <div className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap font-normal">
            {message.content}
          </div>

          {/* Articles sources consultables */}
          {message.documents?.length > 0 && (
            <div className="pt-3 border-t border-slate-100">
              <span className="text-xs font-medium text-slate-400 block mb-2">Sources légales consultées :</span>
              <div className="flex flex-wrap gap-2">
                {message.documents.map((doc, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSelectedDocument(doc)}
                    className="inline-flex items-center gap-1.5 text-xs bg-slate-50 hover:bg-emerald-50 text-slate-700 hover:text-emerald-700 border border-slate-200 hover:border-emerald-300 rounded-lg px-2.5 py-1.5 transition"
                  >
                    <BookMarked className="w-3.5 h-3.5 text-slate-400" />
                    <span>{doc.source} - {doc.article_no}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <span className="block text-[10px] text-slate-400 mt-2">{message.timestamp}</span>
        </div>
      </div>
    </div>
  );
};