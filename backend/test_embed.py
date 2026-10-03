import ollama

res = ollama.embed(
    model="bge-m3", input="إذا قدم الخاطب الصداق وحدث عدول عن الخطبة"
)
# Affiche la dimension du vecteur (1024 dimensions pour bge-m3)
print("Succès ! Dimension du vecteur :", len(res.embeddings[0]))