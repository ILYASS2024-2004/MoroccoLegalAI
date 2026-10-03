import json
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agent.state import LegalCategory
from retriever import HybridLegalRetriever

# Instance unique du retriever (chargée une seule fois en RAM)
retriever = HybridLegalRetriever()


class LegalSearchInput(BaseModel):
    query: str = Field(
        description="Requête formulée en arabe juridique marocain optimisée pour la recherche (BM25 + Dense)."
    )
    category: Optional[LegalCategory] = Field(
        default=None,
        description=(
            "Filtre strict selon le domaine concerné :\n"
            "- 'famille' : mariage, divorce, نفقة, حضانة, héritage\n"
            "- 'travail' : licenciement, salaire, contrat, patron, congés\n"
            "- 'procedure_civile' : compétence judiciaire, assignation, délais de recours\n"
            "- 'procedure_penale' : infractions, police judiciaire, garde à vue\n"
            "- 'commerce' : fonds de commerce, faillite, chèques, sociétés\n"
            "- 'civil' : obligations générales, contrats de vente, loyer, responsabilité (DOC)"
        ),
    )


@tool("search_moroccan_law", args_schema=LegalSearchInput)
def search_moroccan_law(
    query: str, category: Optional[LegalCategory] = None
) -> str:
    """Recherche des articles de lois officiels dans le corpus juridique marocain.

    À exécuter pour chaque question nécessitant une base textuelle légale.
    """
    print(
        f"\n[Tool Execution] Categorie: '{category}' | Requete: '{query[:50]}...'"
    )

    docs = retriever.search(query=query, category=category, top_k=4)

    if not docs:
        return json.dumps(
            {
                "status": "empty",
                "message": "Aucun article correspondant trouvé dans cette catégorie.",
            },
            ensure_ascii=False,
        )

    # Formatage structuré JSON pour faciliter la lecture et la validation par l'agent
    payload = [
        {
            "source": d["source"],
            "article_no": d["article_no"],
            "category": d["category"],
            "text": d["text"],
        }
        for d in docs
    ]
    return json.dumps(payload, ensure_ascii=False)


# Liste des outils distribuables à l'agent
LEGAL_TOOLS = [search_moroccan_law]