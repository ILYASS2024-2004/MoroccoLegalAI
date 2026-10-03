from pydantic import BaseModel


class LegalChunk(BaseModel):
    chunk_id: str             # ex: "code_travail_art_39"
    text: str                 # Texte de l'article avec son titre hiérarchique
    source: str               # ex: "مدونة الشغل"
    article_no: str           # ex: "المادة 39" ou "الفصل 264"
    page_start: int           # Page de début
    page_end: int             # Page de fin (si l'article s'étend sur 2 pages)
    category: str             # ex: "travail", "famille", "penal", "civil", "commerce"