import os
import re
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from retriever import HybridLegalRetriever

# =====================================================================
# 1. ÉTAT GLOBAL DU GRAPHE (State Contract)
# =====================================================================

LegalCategory = Literal[
    "famille",
    "travail",
    "commerce",
    "procedure_civile",
    "procedure_penale",
    "civil",
]


class LegalAgentState(TypedDict):
    # Entrée et conversation
    user_input: str
    chat_history: List[Dict[str, str]]

    # Faits et mémoire du dossier
    case_facts: Dict[str, Any]
    past_queries: List[str]
    retries: int

    # Données d'orchestration
    target_category: Optional[LegalCategory]
    rewritten_query: str
    documents: List[Dict[str, Any]]
    generation: str

    # Évaluation de l'AI Judge
    verification_status: Literal[
        "pass", "bad_retrieval", "bad_generation", "missing_info"
    ]
    judge_critique: str


# =====================================================================
# 2. SCHÉMAS PYDANTIC POUR SORTIES STRUCTURÉES
# =====================================================================


class CaseFactsUpdate(BaseModel):
    extracted_facts: Dict[str, str] = Field(
        description="Faits juridiques clés extraits ou mis à jour (ex: type de contrat, motif, durée, liens familiaux)."
    )
    is_missing_critical_info: bool = Field(
        default=False,
        description="Vrai si les faits sont insuffisants ou trop contradictoires pour qualifier juridiquement le cas.",
    )


class QueryRewriterOutput(BaseModel):
    target_category: Optional[LegalCategory] = Field(
        default=None,
        description="Code juridique marocain applicable (famille, travail, commerce, procedure_civile, procedure_penale, civil).",
    )
    search_query: str = Field(
        description="Requête ultra-précise en arabe juridique marocain optimisée pour BM25 et vecteurs."
    )


class JudgeEvaluation(BaseModel):
    status: Literal["pass", "bad_retrieval", "bad_generation", "missing_info"] = (
        Field(
            description=(
                "- 'pass': Réponse rigoureuse, fidèle aux articles et sourcée.\n"
                "- 'bad_retrieval': Les articles récupérés ne répondent pas du tout au cas posé.\n"
                "- 'bad_generation': Les articles sont bons, mais le LLM hallucine ou ne cite pas la source.\n"
                "- 'missing_info': Il manque un fait juridique déterminant pour trancher."
            )
        )
    )
    critique: str = Field(
        description="Explication précise du verdict et instructions correctives."
    )


# =====================================================================
# 3. INITIALISATION DU MODÈLE ET DES SERVICES
# =====================================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
    google_api_key=os.environ.get("GEMINI_API_KEY"),
)

retriever = HybridLegalRetriever()
MAX_RETRIES = 2

# =====================================================================
# 4. LES NŒUDS DU WORKFLOW (Nodes)
# =====================================================================


def update_case_node(state: LegalAgentState) -> Dict[str, Any]:
    """Nœud 1 : Met à jour la fiche de faits (case_facts) sans perdre l'historique."""
    structured_llm = llm.with_structured_output(CaseFactsUpdate)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Tu es un juriste greffier. Analyse le nouveau message de l'utilisateur "
                "et mets à jour la fiche des faits de l'affaire. Ne retiens que les faits matériels pertinents.",
            ),
            (
                "human",
                "Faits actuels : {current_facts}\n\nNouveau message : {message}",
            ),
        ]
    )

    chain = prompt | structured_llm
    res: CaseFactsUpdate = chain.invoke(
        {
            "current_facts": state.get("case_facts", {}),
            "message": state["user_input"],
        }
    )

    updated_facts = state.get("case_facts", {}).copy()
    updated_facts.update(res.extracted_facts)

    return {
        "case_facts": updated_facts,
        "verification_status": (
            "missing_info" if res.is_missing_critical_info else "pass"
        ),
    }


def rewrite_node(state: LegalAgentState) -> Dict[str, Any]:
    """Nœud 2 : Traduit en arabe juridique, extrait les mots-clés et cible la catégorie."""
    structured_llm = llm.with_structured_output(QueryRewriterOutput)

    critique_context = (
        f"\nFeedback de l'essai précédent : {state['judge_critique']}"
        if state.get("judge_critique")
        else ""
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Tu es un expert juriste marocain. À partir des faits établis et de la question, "
                "identifie le code de loi marocain (category) et génère une requête de recherche formelle en arabe.{critique}",
            ),
            (
                "human",
                "Faits de l'affaire : {facts}\nQuestion : {user_input}\nRequêtes déjà tentées : {past_queries}",
            ),
        ]
    )

    chain = prompt | structured_llm
    res: QueryRewriterOutput = chain.invoke(
        {
            "facts": state.get("case_facts", {}),
            "user_input": state["user_input"],
            "past_queries": state.get("past_queries", []),
            "critique": critique_context,
        }
    )

    past = state.get("past_queries", []).copy()
    past.append(res.search_query)

    return {
        "target_category": res.target_category,
        "rewritten_query": res.search_query,
        "past_queries": past,
    }


def retrieve_node(state: LegalAgentState) -> Dict[str, Any]:
    """Nœud 3 : Exécute la recherche hybride (Dense + BM25 + RRF) avec le filtre de catégorie."""
    docs = retriever.search(
        query=state["rewritten_query"],
        category=state["target_category"],
        top_k=4,
    )
    return {"documents": docs}


def generate_node(state: LegalAgentState) -> Dict[str, Any]:
    """Nœud 4 : Génération rigoureuse avec citations formelles."""
    context_blocks = [
        f"[{d['source']} | {d['article_no']}]\n{d['text']}"
        for d in state["documents"]
    ]
    context_str = "\n\n---\n\n".join(context_blocks)

    feedback_instruction = (
        f"\nATTENTION : Corrige impérativement le défaut suivant de ta version précédente : {state['judge_critique']}\n"
        if state.get("verification_status") == "bad_generation"
        else ""
    )

    prompt = f"""Tu es un conseiller juridique expert en droit marocain. Réponds à la question du justiciable.

RÈGLES D'OR :
1. Base-toi EXCLUSIVEMENT sur les articles juridiques fournis dans le contexte.
2. Interdiction formelle d'inventer des lois, numéros d'articles ou conditions non écrites.
3. Cite systématiquement le nom du code et le numéro d'article précis.
4. Réponds dans la langue de la question de l'utilisateur (français, arabe ou darija).
{feedback_instruction}
CONTEXTE JURIDIQUE OFFICIEL :
{context_str}

FAITS DU DOSSIER :
{state.get('case_facts', {})}

QUESTION DU JUSTICIABLE :
{state['user_input']}
"""

    response = llm.invoke(prompt)
    return {"generation": response.content}


def verify_judge_node(state: LegalAgentState) -> Dict[str, Any]:
    """Nœud 5 (AI Judge) : Vérification sur deux niveaux (Logiciel strict + LLM Faithfulness)."""
    generation = state["generation"]
    docs = state["documents"]

    # -------------------------------------------------------------
    # Niveau 1 : Vérification logicielle stricte (Métadonnées)
    # -------------------------------------------------------------
    if not docs:
        return {
            "verification_status": "bad_retrieval",
            "judge_critique": "Aucun document n'a été récupéré pour cette requête.",
            "retries": state.get("retries", 0) + 1,
        }

    valid_articles = {d["article_no"].strip() for d in docs}

    # Extraction regex des mentions d'articles cités dans la génération (ex: المادة 178 ou الفصل 527)
    cited_articles = re.findall(
        r"(?:المادة|الفصل)\s+(\d+)", generation, re.UNICODE
    )

    for cited_num in cited_articles:
        # Vérifie si le numéro cité fait bien partie des documents fournis
        matches = [num for num in valid_articles if cited_num in num]
        if not matches:
            return {
                "verification_status": "bad_generation",
                "judge_critique": (
                    f"Hallucination de citation : L'article {cited_num} est cité dans la réponse "
                    f"mais ne figure pas dans les articles officiellement extraits ({valid_articles})."
                ),
                "retries": state.get("retries", 0) + 1,
            }

    # -------------------------------------------------------------
    # Niveau 2 : Vérification LLM (Groundedness & Faithfulness)
    # -------------------------------------------------------------
    judge_llm = llm.with_structured_output(JudgeEvaluation)

    context_str = "\n".join(
        [f"- {d['source']} {d['article_no']}: {d['text']}" for d in docs]
    )

    judge_prompt = f"""Tu es un juge d'évaluation d'intégrité juridique (Faithfulness Grader).
Évalue si la réponse rédigée respecte rigoureusement les articles fournis sans aucune invention ni dérive.

CONTEXTE FOURNI :
{context_str}

RÉPONSE DU MODÈLE :
{generation}

Critères de décision :
- 'pass' : Tout ce qui est affirmé découle directement des textes cités.
- 'bad_generation' : Le modèle extrapole, interprète mal la condition ou oublie de sourcer.
- 'bad_retrieval' : Les articles récupérés ne permettent manifestement pas de répondre au problème posé.
"""

    eval_result: JudgeEvaluation = judge_llm.invoke(judge_prompt)

    return {
        "verification_status": eval_result.status,
        "judge_critique": eval_result.critique,
        "retries": state.get("retries", 0) + (
            1 if eval_result.status != "pass" else 0
        ),
    }


# =====================================================================
# 5. ROUTAGE ET ARÊTES CONDITIONNELLES (Conditional Edges)
# =====================================================================


def route_after_update(
    state: LegalAgentState,
) -> Literal["rewrite", "clarify"]:
    if state.get("verification_status") == "missing_info":
        return "clarify"
    return "rewrite"


def route_after_judge(
    state: LegalAgentState,
) -> Literal["pass", "bad_retrieval", "bad_generation", "max_retries_exit"]:
    # Garde-fou anti-boucle infinie
    if state.get("retries", 0) >= MAX_RETRIES:
        return "max_retries_exit"

    status = state.get("verification_status", "pass")
    if status == "bad_retrieval":
        return "bad_retrieval"
    elif status == "bad_generation":
        return "bad_generation"
    return "pass"


def clarify_node(state: LegalAgentState) -> Dict[str, Any]:
    """Nœud de sortie si l'affaire manque d'éléments essentiels."""
    return {
        "generation": (
            "Les faits communiqués sont insuffisants pour caractériser juridiquement la situation. "
            "Pourriez-vous préciser les conditions exactes de votre contrat ou de votre litige ?"
        )
    }


def max_retries_node(state: LegalAgentState) -> Dict[str, Any]:
    """Nœud de sécurité en cas d'échec répété de la boucle d'autocorrection."""
    return {
        "generation": (
            f"Note de prudence : Malgré plusieurs tentatives d'autocorrection, "
            f"le système n'a pas pu certifier à 100% la concordance des textes de loi.\n\n"
            f"Dernière ébauche générée :\n{state.get('generation')}\n\n"
            f"Point d'attention relevé par le vérificateur : {state.get('judge_critique')}"
        )
    }


# =====================================================================
# 6. ASSEMBLAGE DU STATEGRAPH COMPLET
# =====================================================================

workflow = StateGraph(LegalAgentState)

# Ajout des nœuds
workflow.add_node("update_case", update_case_node)
workflow.add_node("clarify", clarify_node)
workflow.add_node("rewrite", rewrite_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("verify_judge", verify_judge_node)
workflow.add_node("max_retries_exit", max_retries_node)

# Flux d'entrée
workflow.add_edge(START, "update_case")

# Branchement conditionnel après qualification des faits
workflow.add_conditional_edges(
    "update_case",
    route_after_update,
    {"clarify": "clarify", "rewrite": "rewrite"},
)

workflow.add_edge("clarify", END)

# Séquence nominale de recherche et génération
workflow.add_edge("rewrite", "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "verify_judge")

# Boucles d'autocorrection (Self-RAG / CRAG)
workflow.add_conditional_edges(
    "verify_judge",
    route_after_judge,
    {
        "pass": END,
        "bad_retrieval": "rewrite",  # Boucle 1 : reformule la requête
        "bad_generation": "generate",  # Boucle 2 : regénère avec feedback
        "max_retries_exit": "max_retries_exit",
    },
)

workflow.add_edge("max_retries_exit", END)

# Compilation du graphe
legal_graph = workflow.compile()