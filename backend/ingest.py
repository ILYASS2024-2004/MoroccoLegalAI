import os
import json
from parser import MoroccanLegalParser
from schema import LegalChunk

# Configuration des 6 codes retenus avec leurs nouveaux noms exacts
DOCUMENTS_CONFIG = [
    {
        "filename": "مدونة الأسرة-9-87.pdf",
        "source": "مدونة الأسرة",
        "category": "famille"
    },
    {
        "filename": "مدونة الشغل-2-106.pdf",
        "source": "مدونة الشغل",
        "category": "travail"
    },
    {
        "filename": "مدونة-التجارة-4-174.pdf",
        "source": "مدونة التجارة",
        "category": "commerce"
    },
    {
        "filename": "قانون الالتزامات والعقود-5-258.pdf",
        "source": "قانون الالتزامات والعقود",
        "category": "civil"
    },
    {
        "filename": "الجنائية المسطرة -25-314.pdf",
        "source": "قانون المسطرة الجنائية",
        "category": "procedure_penale"
    },
    {
        "filename": "قانون_المسطرة_المدنية_(المغرب)-5-128.pdf",
        "source": "قانون المسطرة المدنية",
        "category": "procedure_civile"
    }
]

def load_all_documents(pdf_dir: str = "PDFs") -> list[LegalChunk]:
    all_chunks: list[LegalChunk] = []
    
    print("=" * 60)
    print("EXTRACTION GLOBALE DES 6 CODES JURIDIQUES")
    print("=" * 60)

    for doc in DOCUMENTS_CONFIG:
        filepath = os.path.join(pdf_dir, doc["filename"])
        
        if not os.path.exists(filepath):
            print(f"[!] Fichier manquant dans le dossier PDFs/ : {filepath}")
            continue

        print(f"\n[+] Traitement : {doc['source']} ({doc['filename']})...")
        parser = MoroccanLegalParser(source_name=doc["source"], category=doc["category"])
        
        try:
            chunks = parser.parse_pdf(filepath)
            print(f"    -> Succès : {len(chunks)} articles extraits.")
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"    [X] Erreur sur {filepath} : {e}")

    print("\n" + "=" * 60)
    print(f"TOTAL GÉNÉRAL : {len(all_chunks)} articles extraits.")
    print("=" * 60)
    
    return all_chunks

def export_chunks_to_json(chunks: list[LegalChunk], output_file: str = "chunks.json"):
    data = [chunk.model_dump() for chunk in chunks]
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n[+] Base sauvegardée dans '{output_file}' ({len(chunks)} articles).")

if __name__ == "__main__":
    chunks = load_all_documents()
    if chunks:
        export_chunks_to_json(chunks)