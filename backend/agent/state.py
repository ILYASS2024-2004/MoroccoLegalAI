from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

LegalCategory = Literal[
    "famille",  # مدونة الأسرة
    "travail",  # مدونة الشغل
    "commerce",  # مدونة التجارة
    "procedure_civile",  # قانون المسطرة المدنية
    "procedure_penale",  # قانون المسطرة الجنائية
    "civil",  # قانون الالتزامات والعقود
]


# Schémas de validation Pydantic pour les décisions intermédiaires


class CaseFactsUpdate(BaseModel):
    extracted_facts: Dict[str, str] = Field(
        default_factory=dict,
        description="Faits juridiques matériels extraits (ex: litige: non-paiement heures sup, durée: 2 mois).",
    )
    is_missing_info: bool = Field(
        default=False,
        description=(
            "Mettre True UNIQUEMENT si le message est totalement vide d'éléments juridiques "
            "(ex: 'bonjour', 'aidez-moi', 'j'ai un problème'). "
            "Dès que l'utilisateur évoque une situation concrète (heures supplémentaires, licenciement, divorce, etc.), "
            "mettre impérativement False."
        ),
    )



class QueryRewriteOutput(BaseModel):
    standalone_question: str = Field(
        ...,
        description="La question de l'utilisateur réécrite de manière complète et autonome, intégrant tout le contexte de la conversation précédente, sans aucun pronom ni ambiguïté.",
    )
    target_category: Literal[
        "famille",
        "travail",
        "procedure_civile",
        "procedure_penale",
        "doc",
        "commerce",
        "general",
    ] = Field(
        ...,
        description="Le code de loi marocain applicable déduit de la question autonome.",
    )
    search_query: str = Field(
        ...,
        description="Requête de recherche en arabe juridique pur (mots-clés pertinents sans noms de codes ni lois).",
    )

class JudgeEvaluation(BaseModel):
    status: Literal["pass", "bad_retrieval", "bad_generation"] = Field(
        description=(
            "- 'pass': La réponse découle strictement des textes et cite les vrais articles.\n"
            "- 'bad_retrieval': Les articles récupérés sont hors sujet par rapport au litige.\n"
            "- 'bad_generation': Hallucination, interprétation erronée ou absence de citation d'articles."
        )
    )
    critique: str = Field(
        description="Feedback constructif indiquant au LLM ce qui doit être corrigé."
    )


# Contrat d'état (State) conforme à votre Layer 3


class LegalAgentState(TypedDict):
    # Entrée et mémoire conversationnelle
    user_input: str
    chat_history: List[Dict[str, str]]

    # Dossier juridique
    case_facts: Dict[str, Any]
    past_queries: List[str]
    retries: int

    # Données du pipeline RAG
    target_category: Optional[LegalCategory]
    rewritten_query: str
    documents: List[Dict[str, Any]]
    generation: str

    # Jugement et boucle d'autocorrection
    verification_status: Literal[
        "pass", "bad_retrieval", "bad_generation", "missing_info"
    ]
    judge_critique: str