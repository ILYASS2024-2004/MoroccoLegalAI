import React from 'react';
import { X, BookOpen, Scale } from 'lucide-react';
import { useChatStore } from '../store/useChatStore';

export const LegalDrawer = () => {
  const { selectedDocument, setSelectedDocument } = useChatStore();

  if (!selectedDocument) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white border-l border-slate-200 shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-in-out">
      <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-2 text-slate-800">
          <Scale className="w-5 h-5 text-emerald-600" />
          <h3 className="font-semibold text-sm">Source Légale Officielle</h3>
        </div>
        <button
          onClick={() => setSelectedDocument(null)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="p-5 flex-1 overflow-y-auto space-y-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded">
            {selectedDocument.source}
          </span>
          <h2 className="text-lg font-bold text-slate-900 mt-2">
            {selectedDocument.article_no}
          </h2>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs font-medium text-slate-400 mb-2">TEXTE OFFICIEL (ARABE) :</p>
          <div
            dir="rtl"
            className="p-4 bg-slate-50 rounded-xl text-slate-800 leading-relaxed font-serif text-sm border border-slate-200/60 shadow-inner"
          >
            {selectedDocument.text}
          </div>
        </div>
      </div>
    </div>
  );
};