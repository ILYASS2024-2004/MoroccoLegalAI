import os
import re
import pymupdf as fitz
from pydantic import BaseModel

class LegalChunk(BaseModel):
    chunk_id: str             # ex: "code_travail_art_39"
    text: str                 # Texte de l'article pur
    source: str               # ex: "مدونة الشغل"
    article_no: str           # ex: "المادة 39" ou "الفصل 264"
    page_start: int           # Page de début
    page_end: int             # Page de fin
    category: str             # ex: "travail", "famille", "penal"


class MoroccanLegalParser:
    TASHKEEL_REGEX = re.compile(r"[\u064B-\u065F\u0670]")
    BIDI_REGEX = re.compile(
        r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\u200b\u200c\u200d\u00a0\xad]"
    )

    NOISE_PATTERNS = [
        r"^المملكة\s+المغربية.*$",
        r"^وزارة\s+العدل.*$",
        r"^مديرية\s+التشريع.*$",
        r"^رئاسة\s+النيابة\s+العامة.*$",
        r"^وحدة\s+الدراسات\s+والتوثيق.*$",
        r"^عدالة.*$",
        r"^[-–—]?\s*\d+\s*[-–—]?$",
        # إضافة العناوين الهيكلية كشوائب حتى لا يتم دمجها مع نص المادة
        r"^[\s]*(الكتاب|القسم|الباب|الفرع)\s+[^\n:]+" 
    ]

    ARTICLE_INLINE_PATTERN = re.compile(
        r"^[\s]*((?:الماد[ةه]|الفصل))\s*[:\.\-–]?\s*(\d+(?:[\.\-–]\d+)?|الأول[ى]?)(?:\s+(?:مكرر[ة]?|مكرر\s+مرتين|مكرر\s+ثالث\s+مرات))?(?!\s*(?:أعلاه|بعده|أدناه|السالف|من\s+قانون|من\s+الظهير|من\s+القانون|من\s+هذ[اه]))(?:\s*[:\.\-–]|\s+|$)"
    )

    ARTICLE_ALONE_PATTERN = re.compile(r"^[\s]*((?:الماد[ةه]|الفصل))\s*[:\.\-–]?$")

    NUMBER_ALONE_PATTERN = re.compile(
        r"^[\s]*(\d+(?:[\.\-–]\d+)?|الأول[ى]?)(?:\s+(?:مكرر[ة]?|مكرر\s+مرتين|مكرر\s+ثالث\s+مرات))?\s*[:\.\-–]?$"
    )

    NUMBER_THEN_TEXT_PATTERN = re.compile(
        r"^[\s]*(\d+(?:[\.\-–]\d+)?|الأول[ى]?)(?:\s+(?:مكرر[ة]?|مكرر\s+مرتين|مكرر\s+ثالث\s+مرات))?(?!\s*(?:أعلاه|بعده|أدناه))(?:\s*[:\.\-–]|\s+)(.*)$"
    )

    FOOTNOTE_PATTERN = re.compile(
        r"^[\s]*\d+(?:\[\d+\])?\s*[-–]\s*(?:الجريدة\s+الرسمية|ظهير|قانون\s+رقم|مرسوم|قرار|تم\s+|يراجع|المقصود|ينص|قارن|انظر|حلت|أضيفت|وردت|المقصود|تَمَّم|نَسَخَت).*"
    )

    ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

    def __init__(self, source_name: str, category: str):
        self.source_name = source_name
        self.category = category
        self.noise_re = re.compile("|".join(f"(?:{p})" for p in self.NOISE_PATTERNS))

    def _normalize(self, text: str) -> str:
        text = self.BIDI_REGEX.sub(" ", text)
        text = self.TASHKEEL_REGEX.sub("", text)
        text = re.sub(r"ـ+", "", text)
        text = text.translate(self.ARABIC_INDIC_DIGITS)
        text = re.sub(r"المادة\s+215(?=\s|$)", "المادة 15", text)
        text = re.sub(r"^11248\s+المادة", "المادة 248", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def parse_pdf(self, pdf_path: str) -> list[LegalChunk]:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Fichier introuvable : '{pdf_path}'")

        doc = fitz.open(pdf_path)
        chunks = []

        current_article_no = None
        current_article_lines = []
        current_page_start = 1

        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            raw_lines = doc[page_idx].get_text("text").split("\n")

            lines = [self._normalize(l) for l in raw_lines]
            lines = [l for l in lines if l]

            in_footnote = False

            i = 0
            while i < len(lines):
                line = lines[i]

                if self.FOOTNOTE_PATTERN.match(line):
                    in_footnote = True
                    i += 1
                    continue
                
                if in_footnote:
                    if not (self.ARTICLE_INLINE_PATTERN.match(line) or self.ARTICLE_ALONE_PATTERN.match(line)):
                        i += 1
                        continue
                    else:
                        in_footnote = False 

                matched_article_no = None
                remainder_text = ""

                inline_match = self.ARTICLE_INLINE_PATTERN.match(line)
                if inline_match:
                    keyword = inline_match.group(1).strip()
                    num = inline_match.group(2).strip()
                    matched_article_no = f"{keyword} {num}"
                    remainder_text = line[inline_match.end() :].strip()
                    i += 1
                elif self.ARTICLE_ALONE_PATTERN.match(line) and (i + 1 < len(lines)):
                    alone_match = self.ARTICLE_ALONE_PATTERN.match(line)
                    keyword = alone_match.group(1).strip()
                    next_line = lines[i + 1]

                    if self.NUMBER_ALONE_PATTERN.match(next_line):
                        num_match = self.NUMBER_ALONE_PATTERN.match(next_line)
                        matched_article_no = f"{keyword} {num_match.group(1).strip()}"
                        remainder_text = ""
                        i += 2
                    elif self.NUMBER_THEN_TEXT_PATTERN.match(next_line):
                        num_match = self.NUMBER_THEN_TEXT_PATTERN.match(next_line)
                        matched_article_no = f"{keyword} {num_match.group(1).strip()}"
                        remainder_text = num_match.group(2).strip()
                        i += 2
                    else:
                        i += 1

                if matched_article_no:
                    if current_article_no and current_article_lines:
                        chunks.append(
                            self._create_chunk(
                                article_no=current_article_no,
                                lines=current_article_lines,
                                page_start=current_page_start,
                                page_end=page_num,
                            )
                        )

                    current_article_no = matched_article_no
                    current_article_lines = []
                    current_page_start = page_num

                    if remainder_text:
                        current_article_lines.append(remainder_text)
                else:
                    if self.noise_re.match(line):
                        # يتم تخطي العناوين الهيكلية (الكتاب، الباب...) وأرقام الصفحات هنا
                        i += 1
                        continue

                    if current_article_no:
                        current_article_lines.append(line)
                    i += 1

        if current_article_no and current_article_lines:
            chunks.append(
                self._create_chunk(
                    article_no=current_article_no,
                    lines=current_article_lines,
                    page_start=current_page_start,
                    page_end=len(doc),
                )
            )

        doc.close()
        return chunks

    def _create_chunk(self, article_no: str, lines: list[str], page_start: int, page_end: int) -> LegalChunk:
        safe_id = re.sub(r"\s+", "_", article_no.replace("-", "_").replace(".", "_"))
        chunk_id = f"{self.category}_{safe_id}"

        raw_body = " ".join([l.strip() for l in lines if l.strip()])

        # 1. Supprimer les tirets et points résiduels en fin de texte
        clean_body = re.sub(r"[\s\-–—\.]+$", "", raw_body).strip()

        # 2. Supprimer les points isolés au milieu des phrases (ex: "ب .ها" ou "أو .طبقا")
        clean_body = re.sub(r"\s+\.\s*", " ", clean_body)

        # 3. Supprimer les espaces avant les lettres isolées courantes en arabe
        clean_body = re.sub(r"\s+([ـةه])", r"\1", clean_body)

        enriched_text = f"[{self.source_name} | {article_no}]\n{clean_body}"

        return LegalChunk(
            chunk_id=chunk_id,
            text=enriched_text,
            source=self.source_name,
            article_no=article_no,
            page_start=page_start,
            page_end=page_end,
            category=self.category,
        )

    def fix_broken_arabic_words(self, text: str) -> str:
        """
        Recolle les lettres arabes séparées par des espaces artificiels dans le PDF.
        Ne fusionne que les lettres qui s'attachent obligatoirement à gauche.
        """
        connecting_letters = "بتثجحخسشصضطظعغفقكلمنهي"
        pattern = rf"([{connecting_letters}])\s+([\u0621-\u064A])"

        # Répéter 2 fois pour les mots morcelés en 3 parties (ex: "ال دي بل وما")
        text = re.sub(pattern, r"\1\2", text)
        text = re.sub(pattern, r"\1\2", text)
        return text