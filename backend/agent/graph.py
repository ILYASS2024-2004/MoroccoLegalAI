from typing import Literal
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver  # 1. Import
from agent.nodes import (
    clarify_node,
    generate_node,
    max_retries_node,
    retrieve_node,
    rewrite_node,
    update_case_node,
    verify_judge_node,
)
from agent.state import LegalAgentState

MAX_RETRIES = 2


# Arête conditionnelle 1 : Après qualification des faits
def route_after_update(
    state: LegalAgentState,
) -> Literal["rewrite", "clarify"]:
    if state.get("verification_status") == "missing_info":
        return "clarify"
    return "rewrite"


# Arête conditionnelle 2 : Après l'évaluation de l'AI Judge (Self-Correction)
def route_after_judge(
    state: LegalAgentState,
) -> Literal["pass", "bad_retrieval", "bad_generation", "max_retries"]:
    if state.get("retries", 0) >= MAX_RETRIES:
        return "max_retries"

    status = state.get("verification_status", "pass")
    if status == "bad_retrieval":
        return "bad_retrieval"  # Reboucle vers Rewrite
    elif status == "bad_generation":
        return "bad_generation"  # Reboucle vers Generate
    return "pass"  # Succès -> Sortie directe vers React


# Assemblage du Graphe
builder = StateGraph(LegalAgentState)

# 1. Enregistrement des 5 nœuds cœurs + 2 nœuds de sécurité
builder.add_node("update_case", update_case_node)
builder.add_node("clarify", clarify_node)
builder.add_node("rewrite", rewrite_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("generate", generate_node)
builder.add_node("verify_judge", verify_judge_node)
builder.add_node("max_retries", max_retries_node)

# 2. Branchement initial
builder.add_edge(START, "update_case")

builder.add_conditional_edges(
    "update_case",
    route_after_update,
    {
        "clarify": "clarify",
        "rewrite": "rewrite",
    },
)
builder.add_edge("clarify", END)

# 3. Chaîne séquentielle nominale
builder.add_edge("rewrite", "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", "verify_judge")

# 4. Arêtes conditionnelles du Judge (Les 3 cas de sortie)
builder.add_conditional_edges(
    "verify_judge",
    route_after_judge,
    {
        "pass": END,
        "bad_retrieval": "rewrite",  # Boucle 1 : reformule la recherche
        "bad_generation": "generate",  # Boucle 2 : regénère avec feedback
        "max_retries": "max_retries",
    },
)
builder.add_edge("max_retries", END)

# Compilation du graphe d'état
checkpointer = MemorySaver()
legal_agent_graph = builder.compile()