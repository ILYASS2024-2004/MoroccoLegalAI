import os
import re
import uuid
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Chargement forcé des variables d'environnement (.env)
load_dotenv(override=True)

# Import du StateGraph LangGraph configuré avec MemorySaver
from agent.graph import legal_agent_graph

app = FastAPI(
    title="Moroccan Legal AI Agent API",
    description="API REST d'assistance juridique en droit marocain (LangGraph + Gemini + Hybrid Search)",
    version="1.0.0",
)

# Configuration CORS pour autoriser le frontend (React, Vite, Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Modèles de données Pydantic ---


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        description="Question juridique ou situation factuelle de l'utilisateur",
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Identifiant unique de session pour la persistance de l'historique",
    )


class LegalDocument(BaseModel):
    source: str
    article_no: str
    text: str


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    target_category: Optional[str] = None
    verification_status: str
    cited_articles: List[str] = []
    context_articles: List[str] = []
    documents: List[LegalDocument] = []


# --- Endpoints ---


@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "Moroccan Legal Agent API",
        "version": "1.0.0",
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    try:
        # 1. Gestion de l'identifiant de session court-terme
        session_id = payload.thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        # 2. Exécution du StateGraph LangGraph
        result = legal_agent_graph.invoke(
            {"user_input": payload.message}, config=config
        )

        generation_text = result.get("generation", "")
        raw_docs = result.get("documents", [])

        # 3. Extraction des articles mis à disposition par le Retriever
        context_articles = [str(d.get("article_no", "")).strip() for d in raw_docs]

        # 4. Extraction Regex des numéros d'articles réellement cités dans l'argumentaire
        cited_numbers_raw = re.findall(
            r"(?:المادة|الفصل|article|l'article)\s*[\*\_]*\s*(\d+)",
            generation_text,
            re.IGNORECASE | re.UNICODE,
        )
        cited_articles = sorted(list(set(cited_numbers_raw)))

        # 5. Formatage des documents sources pour l'affichage frontend
        docs_formatted = [
            LegalDocument(
                source=d.get("source", ""),
                article_no=str(d.get("article_no", "")),
                text=d.get("text", "")[:350]
                + ("..." if len(d.get("text", "")) > 350 else ""),
            )
            for d in raw_docs
        ]

        return ChatResponse(
            thread_id=session_id,
            answer=generation_text,
            target_category=result.get("target_category"),
            verification_status=result.get("verification_status", "pass"),
            cited_articles=cited_articles,
            context_articles=context_articles,
            documents=docs_formatted,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erreur d'exécution de l'agent : {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)