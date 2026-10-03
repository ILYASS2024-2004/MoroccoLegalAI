
import os
import re
import time
from typing import Any, Dict
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.state import (
    CaseFactsUpdate,
    JudgeEvaluation,
    LegalAgentState,
    QueryRewriteOutput,
)
from retriever import HybridLegalRetriever

load_dotenv()

# Utilisation de max_retries pour encaisser les pics de requêtes de l'API
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0,
    max_retries=6,
    google_api_key=os.environ.get("GEMINI_API_KEY"),
)
retriever = HybridLegalRetriever()


def extract_text(content: Any) -> str:
    """Garantit que le retour du LLM est une chaîne de caractères str."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


# =====================================================================
# NŒUD 1 : UPDATE CASE
# =====================================================================
def update_case_node(state: LegalAgentState) -> Dict[str, Any]:
    print("\n" + "─" * 70)
    print("▶ [1/5] NŒUD : UPDATE CASE (Analyse des faits juridiques)")
    print("─" * 70)
    print(f"  • Message utilisateur : {state['user_input']}")

    structured_llm = llm.with_structured_output(CaseFactsUpdate)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Tu es un juriste analyste en droit marocain.\n"
                "Ta mission est d'extraire les faits de la demande et d'évaluer si une recherche légale est possible.\n\n"
                "RÈGLE SUR LES QUESTIONS DE SUIVI ET DE MONTANT :\n"
                "- Si l'utilisateur pose une question de suivi sur une estimation, un montant ou un délai (ex: 'combien ?', 'comment calculer ?', 'quel est le prix ?'), "
                "ne bloque PAS la recherche ! Mets 'is_missing_info: False'. Le système doit aller extraire les articles fixant les règles et critères d'évaluation légale.\n"
                "- Ne mets 'is_missing_info: True' QUE si le message est totalement incompréhensible ou hors sujet (ex: 'bonjour', 'aide-moi').",
            ),
            (
                "human",
                "Historique récent : {history}\n\nFaits enregistrés : {facts}\n\nNouveau message : {message}",
            ),
        ]
    )

    result: CaseUpdateOutput = (prompt | structured_llm).invoke(
        {
            "history": state.get("chat_history", [])[-4:],
            "facts": state.get("case_facts", {}),
            "message": state["user_input"],
        }
    )

    updated_facts = state.get("case_facts", {}).copy()
    updated_facts.update(result.extracted_facts)

    print(f"  ✓ Faits extraits par le LLM : {result.extracted_facts}")
    print(f"  ✓ Information manquante ?   : {result.is_missing_info}")

    return {
        "case_facts": updated_facts,
        "verification_status": (
            "missing_info" if result.is_missing_info else "pass"
        ),
    }


# =====================================================================
# NŒUD 2 : REWRITE & ROUTING
# =====================================================================
# Nœud 2 : REWRITE avec Persistance Contextuelle Multi-tours
def rewrite_node(state: LegalAgentState) -> Dict[str, Any]:
    print("\n" + "─" * 70)
    print("▶ [2/5] NŒUD : REWRITE (Contextualisation Historique & Traduction)")
    print("─" * 70)

    time.sleep(1.0)

    structured_llm = llm.with_structured_output(QueryRewriteOutput)

    critique_prompt = (
        f"\nCritique corrective du juge au tour précédent : {state.get('judge_critique')}"
        if state.get("judge_critique")
        else ""
    )

    # Formatage propre de l'historique de conversation
    raw_history = state.get("chat_history", [])[-6:]  # Les 3 derniers tours
    formatted_history = "\n".join(
        [
            f"- {'Utilisateur' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in raw_history
        ]
    )
    if not formatted_history:
        formatted_history = "Aucun échange antérieur (début de conversation)."

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Tu es un juriste analyste et documentaliste expert en droit marocain.\n\n"
                "TA MISSION EN 3 ÉTAPES :\n"
                "1. REFORMULATION AUTONOME (STANDALONE) :\n"
                "   Lis l'historique de conversation et le nouveau message de l'utilisateur.\n"
                "   Si le message est court, incomplet ou fait référence à ce qui précède (ex: 'combien ?', 'quel délai ?', 'et s'il refuse ?'), "
                "   fusionne-le avec le sujet en cours pour en faire une question juridique complète, autonome et compréhensible sans avoir lu l'historique.\n"
                "2. QUALIFICATION DE LA BRANCHE DU DROIT :\n"
                "   À partir de la QUESTION AUTONOME ainsi créée, sélectionne le code marocain pertinent (famille, travail, procedure_civile, procedure_penale, doc, commerce).\n"
                "   Ne choisis 'general' QUE si la question autonome touche réellement plusieurs codes ou n'appartient à aucune branche spécifique.\n\n"
                "3. MOTS-CLÉS DE RECHERCHE ARABE :\n"
                "   Génère les termes techniques en arabe juridique pour la recherche hybride (BM25 + Vecteurs).\n"
                "   Exclus impérativement les mots parasites : 'قانون', 'مدونة', 'المغرب', 'فصل', 'مادة'.{critique}",
            ),
            (
                "human",
                "HISTORIQUE DE CONVERSATION :\n{history}\n\n"
                "FAITS ÉTABLIS :\n{facts}\n\n"
                "NOUVEAU MESSAGE UTILISATEUR :\n{question}\n\n"
                "REQUÊTES DÉJÀ TENTÉES :\n{past_queries}",
            ),
        ]
    )

    result: QueryRewriteOutput = (prompt | structured_llm).invoke(
        {
            "history": formatted_history,
            "facts": state.get("case_facts", {}),
            "question": state["user_input"],
            "past_queries": state.get("past_queries", []),
            "critique": critique_prompt,
        }
    )

    print(f"  • Question autonome reformulée : {result.standalone_question}")
    print(f"  • Branche déduite (category)    : {result.target_category}")
    print(f"  • Requête de recherche arabe   : {result.search_query}")

    queries = state.get("past_queries", []).copy()
    queries.append(result.search_query)

    return {
        "target_category": result.target_category,
        "rewritten_query": result.search_query,
        "past_queries": queries,
    }

# =====================================================================
# NŒUD 3 : RETRIEVE (HYBRID SEARCH RRF)
# =====================================================================
def retrieve_node(state: LegalAgentState) -> Dict[str, Any]:
    print("\n" + "─" * 70)
    print("▶ [3/5] NŒUD : RETRIEVE (Recherche hybride ChromaDB + BM25 + RRF)")
    print("─" * 70)
    print(f"  • Recherche avec filtre : category='{state['target_category']}'")
    print(f"  • Requête textuelle     : {state['rewritten_query']}")

    docs = retriever.search(
        query=state["rewritten_query"],
        category=state["target_category"],
        top_k=4,
    )

    print(f"  ✓ Nombre d'articles extraits : {len(docs)}")
    for i, d in enumerate(docs, 1):
        print(f"    [{i}] {d['source']} | {d['article_no']}")
        snippet = d["text"].replace("\n", " ")[:90]
        print(f"        Extrait : {snippet}...")

    return {"documents": docs}


# =====================================================================
# NŒUD 4 : GENERATE
# =====================================================================
def generate_node(state: LegalAgentState) -> Dict[str, Any]:
    print("\n" + "─" * 70)
    print("▶ [4/5] NŒUD : GENERATE (Synthèse juridique argumentée)")
    print("─" * 70)

    # Micro-pause pour protéger le quota RPM
    time.sleep(1.0)

    context_chunks = [
        f"[{d['source']} | {d['article_no']}]\n{d['text']}"
        for d in state["documents"]
    ]
    context_str = "\n\n---\n\n".join(context_chunks)

    corrective_instruction = ""
    if state.get("verification_status") == "bad_generation":
        print(f"  ⚠ Réécriture sous contrainte suite au rejet du Juge !")
        corrective_instruction = f"\nCORRECTION REQUISE : {state.get('judge_critique')}\n"

    prompt = f"""Tu es un conseiller juridique expert en droit marocain. Réponds à la demande.

RÈGLES ABSOLUES :
1. Base-toi EXCLUSIVEMENT sur les articles juridiques fournis ci-dessous.
2. Interdiction formelle d'inventer des numéros d'articles ou des conditions non écrites.
3. Cite systématiquement le nom du code et le numéro d'article.
4. Réponds dans la même langue que la demande.
{corrective_instruction}
ARTICLES JURIDIQUES FOURNIS :
{context_str}

FAITS DU DOSSIER :
{state.get('case_facts', {})}

DEMANDE :
{state['user_input']}
"""

    response = llm.invoke(prompt)
    content = extract_text(response.content)

    print(f"  ✓ Réponse rédigée ({len(content)} caractères)")
    preview = content.replace("\n", " ")[:140]
    print(f"  ✓ Début du texte : {preview}...")

    return {"generation": content}


# =====================================================================
# NŒUD 5 : VERIFY JUDGE (Double niveau)
# =====================================================================
def verify_judge_node(state: LegalAgentState) -> Dict[str, Any]:
    print("\n" + "─" * 70)
    print("▶ [5/5] NŒUD : AI JUDGE (Vérification Regex & Groundedness)")
    print("─" * 70)

    time.sleep(1.0)
    

    generation = extract_text(state.get("generation", ""))
    docs = state.get("documents", [])

    # Niveau 1 : Contrôle Regex
    if not docs:
        print("  ✖ REJET NIVEAU 1 : Aucun document extrait.")
        return {
            "verification_status": "bad_retrieval",
            "judge_critique": "Aucun document juridique trouvé.",
            "retries": state.get("retries", 0) + 1,
        }

    valid_articles = {str(d["article_no"]).strip() for d in docs}

    # Détection multilingue : Arabe (المادة / الفصل), Français (article / l'article) et gras Markdown
    cited_numbers1 = re.findall(
        r"(?:المادة|الفصل|article|l'article)\s*[\*\_]*\s*(\d+)",
        generation,
        re.IGNORECASE | re.UNICODE,
    )
    cited_numbers = list(set(cited_numbers1))
    print(f"  • Articles autorisés dans le contexte : {valid_articles}")
    print(f"  • Articles cités dans la réponse       : {cited_numbers}")

    for cited in cited_numbers:
        # Vérifie si le numéro cité est bien présent dans les métadonnées des articles extraits
        if not any(cited in valid for valid in valid_articles):
            critique = f"Hallucination détectée : l'article {cited} a été cité sans figurer dans le contexte ({valid_articles})."
            print(f"  ✖ REJET NIVEAU 1 (Regex) : {critique}")
            return {
                "verification_status": "bad_generation",
                "judge_critique": critique,
                "retries": state.get("retries", 0) + 1,
            }

    print("  ✓ Validation Regex (Niveau 1) : CONFORME")

# Niveau 2 : Contrôle LLM Faithfulness
    judge_llm = llm.with_structured_output(JudgeEvaluation)
    context_str = "\n".join(
        [f"- {d['source']} {d['article_no']}: {d['text']}" for d in docs]
    )

    judge_prompt = f"""Tu es un juge d'évaluation d'intégrité juridique.
Vérifie si la réponse rédigée découle STRICTEMENT des articles fournis sans extrapolation ni omission majeure.

CONTEXTE FOURNI :
{context_str}

RÉPONSE DU MODÈLE :
{generation}
"""

    eval_result: JudgeEvaluation = judge_llm.invoke(judge_prompt)

    print(f"  • Verdict AI Judge (Niveau 2) : [{eval_result.status.upper()}]")
    print(f"  • Remarque du Juge            : {eval_result.critique}")

    # --- GESTION DE LA MÉMOIRE COURT-TERME ---
    history = list(state.get("chat_history", []))
    if eval_result.status == "pass":
        history.append({"role": "user", "content": state["user_input"]})
        history.append({"role": "assistant", "content": generation})

    return {
        "verification_status": eval_result.status,
        "judge_critique": eval_result.critique,
        "retries": state.get("retries", 0)
        + (1 if eval_result.status != "pass" else 0),
        "chat_history": history,
    }
# =====================================================================
# NŒUDS DE ROUTAGE CONDITIONNEL & SÉCURITÉ
# =====================================================================
def clarify_node(state: LegalAgentState) -> Dict[str, Any]:
    print("\n▶ [!] BIFURCATION : CLARIFICATION DEMANDÉE")
    return {
        "generation": (
            "Les faits communiqués sont insuffisants pour caractériser juridiquement votre situation. "
            "Pourriez-vous préciser le contexte exact de votre contrat ou de votre litige ?"
        )
    }


def max_retries_node(state: LegalAgentState) -> Dict[str, Any]:
    print("\n▶ [!] BIFURCATION : LIMITE MAX DE TENTATIVES ATTEINTE")
    return {
        "generation": (
            f"Note de réserve : Après plusieurs tentatives d'autocorrection, "
            f"une divergence subsiste avec les textes officiels.\n\n"
            f"Dernière ébauche :\n{state.get('generation')}\n\n"
            f"Point d'attention relevé : {state.get('judge_critique')}"
        )
    }