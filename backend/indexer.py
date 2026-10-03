import json
import os
import pickle
import re
import chromadb
import ollama
from rank_bm25 import BM25Okapi
from tqdm import tqdm


def tokenize_arabic(text: str) -> list[str]:
    """Tokenisation pour BM25."""
    clean = re.sub(r"[^\w\s]", " ", text)
    tokens = clean.split()
    return [t for t in tokens if len(t) > 1]


def deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    """
    Fusionne les chunks ayant le même chunk_id pour garantir l'unicité stricte requise par ChromaDB.
    """
    unique_map = {}
    for item in chunks:
        cid = item["chunk_id"]
        if cid not in unique_map:
            unique_map[cid] = item
        else:
            # Si le même article existe en double, on concatène le texte sans dupliquer l'en-tête
            existing_text = unique_map[cid]["text"]
            new_text = item["text"]
            # Enlever l'éventuel en-tête répété
            lines = new_text.split("\n", 1)
            extra_body = lines[1] if len(lines) > 1 else lines[0]
            unique_map[cid]["text"] = f"{existing_text}\n{extra_body}"
            # Étendre la page de fin si nécessaire
            unique_map[cid]["page_end"] = max(
                unique_map[cid]["page_end"], item["page_end"]
            )

    return list(unique_map.values())


def build_indexes(
    json_path: str = "chunks.json",
    chroma_dir: str = "./chroma_db",
    collection_name: str = "moroccan_law",
    bm25_output_path: str = "bm25_index.pkl",
    model_name: str = "bge-m3",
    batch_size: int = 16,
):
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Fichier introuvable : '{json_path}'")

    print("=" * 60)
    print("INDEXATION HYBRIDE : CHROMADB (Dense) + BM25 (Sparse)")
    print(f"Modèle d'embedding : {model_name}")
    print(f"Dossier ChromaDB    : {chroma_dir}")
    print("=" * 60)

    # 1. Charger et dédupliquer strictement les chunks
    with open(json_path, "r", encoding="utf-8") as f:
        raw_chunks = json.load(f)

    chunks = deduplicate_chunks(raw_chunks)
    total = len(chunks)
    print(f"[+] {len(raw_chunks)} articles lus -> {total} articles uniques conservés.")

    # 2. Construction de l'index BM25
    print("\n[+] 1/2 Construction de l'index BM25...")
    tokenized_corpus = [tokenize_arabic(item["text"]) for item in chunks]
    bm25 = BM25Okapi(tokenized_corpus)

    with open(bm25_output_path, "wb") as f:
        pickle.dump(
            {
                "bm25": bm25,
                "chunk_ids": [c["chunk_id"] for c in chunks],
                "chunks": chunks,
            },
            f,
        )
    print(f"    -> Index BM25 sauvegardé dans '{bm25_output_path}'.")

    # 3. Vectorisation et stockage dans ChromaDB
    print("\n[+] 2/2 Vectorisation et stockage dans ChromaDB...")
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"}
    )

    for i in tqdm(range(0, total, batch_size), desc="Vectorisation"):
        batch = chunks[i : i + batch_size]
        texts = [item["text"] for item in batch]
        ids = [item["chunk_id"] for item in batch]
        metadatas = [
            {
                "source": item["source"],
                "article_no": item["article_no"],
                "category": item["category"],
                "page_start": item["page_start"],
                "page_end": item["page_end"],
            }
            for item in batch
        ]

        # Appel direct à Ollama pour obtenir les vecteurs par lot
        response = ollama.embed(model=model_name, input=texts)
        embeddings = response.embeddings

        collection.upsert(
            ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
        )

    print("\n" + "=" * 60)
    print(f"[✓] SUCCÈS : {total} articles indexés dans ChromaDB et BM25 !")
    print("=" * 60)


if __name__ == "__main__":
    build_indexes()