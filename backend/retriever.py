import pickle
import chromadb
from indexer import tokenize_arabic
import ollama


class HybridLegalRetriever:

    def __init__(
        self,
        chroma_dir: str = "./chroma_db",
        collection_name: str = "moroccan_law",
        bm25_path: str = "bm25_index.pkl",
        model_name: str = "bge-m3",
    ):
        # 1. Charger ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=chroma_dir)
        self.collection = self.chroma_client.get_collection(
            name=collection_name
        )
        self.model_name = model_name

        # 2. Charger BM25
        with open(bm25_path, "rb") as f:
            data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.chunk_ids = data["chunk_ids"]
            self.chunks_lookup = {c["chunk_id"]: c for c in data["chunks"]}

    def search(
        self,
        query: str,
        top_k: int = 6,
        alpha: float = 0.7,  # 70% Dense (vecteurs) / 30% Sparse (mots-clés)
        category: str | None = None,
    ) -> list[dict]:
        """Recherche hybride fusionnée (RRF - Reciprocal Rank Fusion) avec filtrage par code juridique."""
        # A. Recherche dense (ChromaDB)
        chroma_filter = {"category": category} if category else None
        q_embed = ollama.embed(model=self.model_name, input=query).embeddings[0]

        dense_res = self.collection.query(
            query_embeddings=[q_embed],
            n_results=top_k * 3,
            where=chroma_filter,
        )

        dense_ranks = {}
        if dense_res["ids"] and len(dense_res["ids"][0]) > 0:
            for rank, c_id in enumerate(dense_res["ids"][0]):
                dense_ranks[c_id] = rank + 1

        # B. Recherche lexicale (BM25) avec filtrage par catégorie
        tokens = tokenize_arabic(query)
        bm25_scores = self.bm25.get_scores(tokens)

        # Trier tous les indices par score décroissant
        sorted_indices = sorted(
            range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
        )

        bm25_ranks = {}
        rank_counter = 1
        for idx in sorted_indices:
            c_id = self.chunk_ids[idx]
            doc = self.chunks_lookup[c_id]

            # Si une catégorie est exigée, on ignore les documents des autres codes
            if category and doc.get("category") != category:
                continue

            bm25_ranks[c_id] = rank_counter
            rank_counter += 1
            if rank_counter > (top_k * 3):
                break

        # C. Fusion RRF (Reciprocal Rank Fusion)
        k_const = 60
        combined_scores = {}
        all_ids = set(dense_ranks.keys()).union(set(bm25_ranks.keys()))

        for c_id in all_ids:
            score = 0.0
            if c_id in dense_ranks:
                score += alpha * (1.0 / (k_const + dense_ranks[c_id]))
            if c_id in bm25_ranks:
                score += (1.0 - alpha) * (1.0 / (k_const + bm25_ranks[c_id]))
            combined_scores[c_id] = score

        # Trier et renvoyer les meilleurs résultats
        sorted_ids = sorted(
            combined_scores.keys(),
            key=lambda x: combined_scores[x],
            reverse=True,
        )[:top_k]

        return [self.chunks_lookup[c_id] for c_id in sorted_ids]


if __name__ == "__main__":
    retriever = HybridLegalRetriever()

    # Test 1 : Question conceptuelle (Sémantique)
    q1 = "ما هي الحالات التي تسقط فيها الحضانة عن الأم بعد الطلاق؟"
    print(f"\n[?] Requête sémantique : {q1}")
    for doc in retriever.search(q1, top_k=2, category="famille"):
        print(f"-> {doc['source']} | {doc['article_no']}")
        print(f"   {doc['text'][:140]}...\n")

    # Test 2 : Requête ciblée par numéro d'article avec filtre explicite
    q2 = "الفصل 527"
    print(f"[?] Requête ciblée avec filtre 'procedure_civile' : {q2}")
    for doc in retriever.search(q2, top_k=1, category="procedure_civile"):
        print(f"-> {doc['source']} | {doc['article_no']}")
        print(f"   {doc['text'][:140]}...\n")