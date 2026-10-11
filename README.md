# MoroccoLegalAI : Architecture RAG Avancee et Agent Juridique Marocain

## Table des matieres

1. [Presentation generale](#presentation-generale)
2. [Objectifs et perimetre fonctionnel](#objectifs-et-perimetre-fonctionnel)
3. [Architecture technique globale](#architecture-technique-globale)
4. [Pipeline d'ingestion et traitement des donnees (ETL)](#pipeline-dingestion-et-traitement-des-donnees-etl)
5. [Moteur de recherche hybride (Retrieval Engine)](#moteur-de-recherche-hybride-retrieval-engine)
6. [Workflow agentique et machine a etats (LangGraph)](#workflow-agentique-et-machine-a-etats-langgraph)
7. [Systeme anti-hallucination a double niveau (AI Judge)](#systeme-anti-hallucination-a-double-niveau-ai-judge)
8. [Corpus juridique et couverture reglementaire](#corpus-juridique-et-couverture-reglementaire)
9. [Architecture logicielle et arborescence](#architecture-logicielle-et-arborescence)
10. [Specifications de l'API Backend (FastAPI)](#specifications-de-lapi-backend-fastapi)
11. [Architecture Frontend (React & Zustand)](#architecture-frontend-react--zustand)
12. [Observabilite et tracabilite (LangSmith)](#observabilite-et-tracabilite-langsmith)
13. [Guide d'installation et de deploiement](#guide-dinstallation-et-de-deploiement)
14. [Guide d'utilisation et scenarios](#guide-dutilisation-et-scenarios)
15. [Avertissement legal (Legal Disclaimer)](#avertissement-legal-legal-disclaimer)

---

## Presentation generale

Qanoon AI est une plateforme d'assistance juridique specialisee dans le droit positif du Royaume du Maroc. Le systeme repose sur une architecture de generation augmentee par recuperation (Retrieval-Augmented Generation - RAG) agentique combinant recherche semantique dense, recherche lexicale creuse, et un graphe d'etat auto-correctif (Corrective RAG / Self-RAG).

Le probleme traite concerne la fiabilite des modeles de langage (LLM) appliques a un corpus reglementaire multilingue (arabe juridique, francais, darija). Les approches RAG conventionnelles echouent frequemment en droit en raison :
- d'hallucinations sur les numeros d'articles de loi ;
- de faux positifs dans l'application croisee de codes de droit differents ;
- de desalignements entre la formulation profane de l'utilisateur et la terminologie doctrinale arabe ;
- de l'absence de persistance des faits juridiques lors d'echanges multi-tours.

Qanoon AI repond a ces defis par un partitionnement strict au niveau de l'article de loi, un routage algorithmique par code juridique, un moteur de recherche hybride avec fusion Reciprocal Rank Fusion (RRF), et un auditeur d'integrite (AI Judge) a deux niveaux d'evaluation.

---

## Objectifs et perimetre fonctionnel

- Consultation juridique guidee : Qualification des faits soumis par le justiciable, detection des faits manquants et demandes de clarification ciblees.
- Analyse multilingue croisee : Prise en charge des requetes exprimees en francais, arabe standard ou arabe dialectal (darija), traduites et enrichies en arabe juridique formel.
- Citations legislatives garanties : Chaque assertion de l'agent est adossee aux textes officiels en vigueur, avec interdiction structurelle d'inventer des references.
- Audit et conformite en temps reel : Attribution d'un statut de verification ("Audite & Conforme" ou "Reserve Juridique") transparent pour l'utilisateur.
- Consultation in-situ des textes de reference : Mise a disposition immediate du texte integral officiel en arabe au format drawer sans rechargement.

---

## Architecture technique globale

Le systeme est scinde en couches techniques distinctes et decouplees :

```
                                +---------------------------+
                                |  Utilisateur (Navigateur)  |
                                +---------------------------+
                                              |
                                              | HTTP / JSON
                                              v
+-----------------------------------------------------------------------------------------+
|                                    INTERFACE FRONTEND                                   |
|   - React 19 + Vite                                                                     |
|   - Tailwind CSS v4 (Design System)                                                     |
|   - Zustand (Gestion d'etat global, threadId & modalite drawer)                        |
+-----------------------------------------------------------------------------------------+
                                              |
                                              | REST API : POST /api/chat
                                              v
+-----------------------------------------------------------------------------------------+
|                                      BACKEND FASTAPI                                    |
|   - app.py : Routage asynchrone, CORS, validation Pydantic                              |
|   - Extraction Regex des references citees                                              |
+-----------------------------------------------------------------------------------------+
                                              |
                                              | Invocations LangGraph (thread_id)
                                              v
+-----------------------------------------------------------------------------------------+
|                              ORCHESTRATION AGENTIQUE (LangGraph)                        |
|                                                                                         |
|    [START]                                                                              |
|       |                                                                                 |
|       v                                                                                 |
|  [update_case] ------------(is_missing_info: True)------------> [clarify] ----> [END]    |
|       |                                                                                 |
|       | (is_missing_info: False)                                                        |
|       v                                                                                 |
|   [rewrite] <---------------------------------------------+                             |
|       |                                                   |                             |
|       v                                                   | (bad_retrieval)             |
|   [retrieve]                                              |                             |
|       |                                                   |                             |
|       v                                                   |                             |
|   [generate] <---------------------+                      |                             |
|       |                            | (bad_generation)     |                             |
|       v                            |                      |                             |
|  [verify_judge] -------------------+                      |                             |
|       |                                                   |                             |
|       +---------------------------------------------------+                             |
|       |                                                                                 |
|       +--(pass)---------------------------------------------------------------> [END]   |
|       |                                                                                 |
|       +--(retries >= 2)-------------------------------------> [max_retries] -> [END]   |
+-----------------------------------------------------------------------------------------+
        |                                                   |
        | Embeddings / BM25 lookup                          | Inferences LLM & Structured Output
        v                                                   v
+-------------------------------------+             +-------------------------------------+
|      MOTEUR DE RECHERCHE HYBRIDE    |             |        MODELES DE FONDATION         |
|  - ChromaDB (Vecteurs denses)       |             |  - Google Gemini 3.5 Flash-lite     |
|  - BGE-M3 (Ollama local / 1024 dim) |             |  - LangSmith (Tracing & Audit)      |
|  - BM25Okapi (Recherche lexicale)   |             +-------------------------------------+
|  - Reciprocal Rank Fusion (RRF)     |
+-------------------------------------+
```

---

## Pipeline d'ingestion et traitement des donnees (ETL)

Le pipeline d'ingestion (`ingest.py` et `parser.py`) transforme les textes legaux officiels bruts au format PDF en unites atomiques structurees et indexables.

### 1. Granularite d'indexation
Contrairement aux methodes classiques de decoupage par fenetre fixe (ex: chunks de 500 caracteres avec chevauchement), Qanoon AI utilise un decoupage logique calque sur l'architecture legislative : **1 chunk = 1 article de loi unique**. Cette regle preserve l'integrite du sens normatif et empeche la rupture de conditions juridiques liees.

### 2. Normalisation et nettoyage NLP de l'arabe juridique
La classe `MoroccanLegalParser` applique des traitements deterministes rigoureux :
- Elimination du Tashkeel (diacritiques arabes) : via l'expression reguliere `[\u064B-\u065F\u0670]`.
- Nettoyage des caracteres de controle bidirectionnels Unicode (Bidi) : elimination des balises `\u200e`, `\u200f`, `\u202a-\u202e`, `\ufeff`.
- Conversion numerique : translitteration des chiffres arabo-indiens (`٠١٢٣٤٥٦٧٨٩`) vers les chiffres arabes standard (`0-9`).
- Suppression du bruit institutionnel : filtrage des mentions recurrentes ("المملكة المغربية", "وزارة العدل", "الجريدة الرسمية", en-tetes ministeriels, paginateurs).
- Elimination des notes de bas de page : detection via `FOOTNOTE_PATTERN` pour eviter la pollution doctrinale ou historique dans le texte normatif.
- Resolution des coupures de mots : fonction `fix_broken_arabic_words` reparant les liaisons typographiques brisees par l'extraction PDF.

### 3. Schema de donnees atomique (`LegalChunk`)
Chaque fragment extrait repond au contrat suivant defini avec Pydantic :

```python
class LegalChunk(BaseModel):
    chunk_id: str        # Identifiant invariant normalise (ex: "travail_المادة_39")
    text: str            # Texte complet de l'article avec en-tete de qualification
    source: str          # Intitule officiel du code (ex: "مدونة الشغل")
    article_no: str      # Numero formate (ex: "المادة 39", "الفصل 264")
    page_start: int      # Numero de page de debut dans le document PDF source
    page_end: int        # Numero de page de fin dans le document PDF source
    category: str        # Categorie d'appartenance (travail, famille, civil, etc.)
```

### 4. Deduplication stricte
La fonction `deduplicate_chunks` dans `indexer.py` assure l'unicite absolue des identifiants `chunk_id` avant insertion. Si un meme article est fragmente sur plusieurs pages ou sections, le corps de texte est concatene proprement sans repetition d'en-tete et la plage de pages est etendue.

---

## Moteur de recherche hybride (Retrieval Engine)

Le composant `HybridLegalRetriever` combine la precision terminologique de la recherche lexicale et la generalisation conceptuelle de la recherche semantique dense.

### 1. Composante dense (ChromaDB + BGE-M3)
- Vector Store : ChromaDB en mode persistant (`PersistentClient`), indexation HNSW avec metrique de distance cosinus (`hnsw:space: cosine`).
- Modele d'embedding : `BAAI/bge-m3` execute localement via Ollama. Ce modele genere des vecteurs denses de 1024 dimensions avec une prise en charge native avancee de la morphologie arabe.
- Filtrage par metadonnee : Application systematique d'un filtre pre-retrieval sur le champ `category` deduit par le nœud de routage.

### 2. Composante lexicale creuse (BM25Okapi)
- Tokenisation dediee : Extraction des lemmes et racines arabes exempts de ponctuation avec seuil de longueur de caractere superieur a 1.
- Stockage de l'index : Serialization pickle (`bm25_index.pkl`) contenant les statistiques de frequence inverse de document (IDF), les identifiants de chunks et la table de projection.
- Filtrage categoriel post-scoring : Exclusion immediate des documents ne correspondant pas a la branche de droit retenue.

### 3. Algorithme de fusion : Reciprocal Rank Fusion (RRF)
Pour fusionner des scores heterogenes (cosinus bornes et scores BM25 non bornes), le systeme utilise l'algorithme RRF avec une constante de lissage \(k = 60\) et une ponderation dense \(\alpha = 0.7\) :

$$Score_{RRF}(d) = \alpha \cdot \frac{1}{k + R_{dense}(d)} + (1 - \alpha) \cdot \frac{1}{k + R_{bm25}(d)}$$

Ce mecanisme assure qu'un article present dans les premiers rangs a la fois en recherche lexicale et en recherche vectorielle sera priorise de maniere deterministe.

---

## Workflow agentique et machine a etats (LangGraph)

Le cœur decisionnel repose sur un graphe d'etat LangGraph (`LegalAgentState`). Chaque interaction utilisateur traverse un cycle de traitement structure et audite.

### Etat global du graphe (`LegalAgentState`)
- `user_input` : Message brut emis par l'utilisateur.
- `chat_history` : Historique des echanges au format messagerie (`role`, `content`).
- `case_facts` : Dictionnaire structure des faits juridiques etablis au fil de l'instruction du dossier.
- `past_queries` : Historique des requetes de recherche tentees (evite la redondance des recherches infructueuses).
- `retries` : Compteur de tentatives de correction (borne a `MAX_RETRIES = 2`).
- `target_category` : Branche de droit assignee (famille, travail, commerce, procedure_civile, procedure_penale, civil, general).
- `rewritten_query` : Requete reformulee en arabe juridique formel.
- `documents` : Liste des articles legaux retournes par le retriever.
- `generation` : Texte de la reponse juridique produite.
- `verification_status` : Statut emis par le validateur (`pass`, `bad_retrieval`, `bad_generation`, `missing_info`).
- `judge_critique` : Feedback detaille explicatif emis en cas de rejet par le juge.

### Description des nœuds du graphe

#### 1. Nœud `update_case` (Analyse des faits)
- Fonction : Extrait les faits juridiquement operants (ex: nature de la rupture, duree de l'anciennete, charges financieres, dates cles) via structured output Pydantic (`CaseFactsUpdate`).
- Decision de bifurcation : Si l'intervention de l'utilisateur est depourvue de toute substance juridique (ex: salutations isolees), le statut bascule en `missing_info` menant vers le nœud `clarify`. Dans le cas contraire, la qualification juridique s'actualise sans ecraser les faits preexistants.

#### 2. Nœud `rewrite` (Contextualisation et traduction juridique)
- Fonction : Transforme la question de l'utilisateur en une interrogation juridique autonome (resolution des anaphores et pronoms se referant aux tours precedents).
- Deducteur de branche : Identifie le code marocain applicable.
- Generateur lexical arabe : Produit les mots-cles techniques en arabe juridique tout en expulsant les termes parasites susceptibles de biaiser BM25 (ex: exclusion de "قانون", "مدونة", "فصل").
- Integration du feedback : Si le nœud est re-invoque suite a un rejet de recherche par le juge, la critique de ce dernier est injectee dans le prompt systeme.

#### 3. Nœud `retrieve` (Execution RRF)
- Fonction : Execute la recherche hybride dense/sparse filtree sur la base des mots-cles generes, en extrayant les 4 articles les plus pertinents.

#### 4. Nœud `generate` (Synthese argumentee sous contrainte)
- Fonction : Redige l'analyse juridique dans la langue initiale de la demande.
- Contraintes de generation :
  - Interdiction absolue d'extrapoler hors des articles fournis dans le bloc de contexte.
  - Obligation de citer le code et le numero d'article exact.
  - Prise en compte imperative de la directive corrective si le tour precedent a ete sanctionne pour mauvaise formulation.

#### 5. Nœud `verify_judge` (Audit d'integrite)
- Evalue la generation sur deux echelons successifs (voir section suivante). Met a jour l'historique conversationnel uniquement si la reponse obtient le statut `pass`.

#### 6. Nœud `clarify` (Demande de precisions)
- Formule une reponse invitant poliment le justiciable a expliciter les parametres indispensables a la qualification de son dossier.

#### 7. Nœud `max_retries` (Garde-fou de reserve)
- S'active si le nombre maximal de boucles correctives est atteint. Restitue l'ebauche produite accompagnee d'une note de reserve technique et des points de divergence souleves par le juge.

---

## Systeme anti-hallucination a double niveau (AI Judge)

L'integrite juridique est securisee par une double barriere de controle implementee dans `verify_judge_node` :

```
             [Reponse generee + Articles du contexte]
                                |
                                v
               +----------------------------------+
               |     NIVEAU 1 : VALIDATION REGEX  |
               +----------------------------------+
               | Extraction de tous les numeros   |
               | d'articles cites dans la reponse |
               | (ex: "المادة 39", "l'article 39") |
               +----------------------------------+
                                |
                Tous les articles cites sont-ils
                 presents dans les metadonnees
                     des documents extraits ?
                     /                   \
                 NON                      OUI
                  /                         \
                 v                           v
     [REJET NIVEAU 1]             +----------------------------------+
  verification_status:            |      NIVEAU 2 : AUDIT LLM        |
    "bad_generation"              |          FAITHFULNESS            |
  retries += 1                    +----------------------------------+
  Boucle vers `generate`          | Verification de la stricte       |
                                  | deduction logique et absence     |
                                  | d'extrapolation                  |
                                  +----------------------------------+
                                             /             \
                                        Echec               Succes (pass)
                                         /                     \
                                        v                       v
                         [REJET NIVEAU 2]               [VALIDATION FINALE]
                      Status: bad_retrieval               Mise a jour historique
                              ou bad_generation           Sortie vers le client
```

### Niveau 1 : Controle logiciel strict (Regex et Metadonnees)
- Expression reguliere multilingue :
  `r"(?:المادة|الفصل|article|l'article)\s*[\*\_]*\s*(\d+)"`
- Analyse d'intersection : Les identifiants extraits de la reponse sont compares a l'ensemble des articles effectivement presents dans le contexte fourni (`valid_articles`).
- Sanction immediate : Si un seul numero d'article cite ne figure pas dans le contexte extrait, l'execution est instantanement rejetee avec le motif :
  `Hallucination detectee : l'article X a ete cite sans figurer dans le contexte.`
  Ce rejet s'effectue sans surcout de token ni inference supplementaire.

### Niveau 2 : Controle sémantique d'inférence (LLM Faithfulness Grader)
- Invoque un modele de langage en mode sortie structuree (`JudgeEvaluation`) pour comparer le sens de la reponse au sens des textes legaux extraits.
- Statuts de sanction :
  - `bad_retrieval` : Les articles extraits sont inadequats pour le cas traite (declenche une re-formulation de requete dans `rewrite`).
  - `bad_generation` : Les articles sont pertinents mais le modele a commis une deduction invalide (declenche une re-generation guidee dans `generate`).
  - `pass` : Argumentation rigoureusement deduite des textes.

---

## Corpus juridique et couverture reglementaire

Le systeme integre 4 204 articles de lois marocaines traites et indexes, repartis sur les six codes fondamentaux :

| Code juridique | Fichier PDF source | Categorie systeme | Volume de regles couvert |
| :--- | :--- | :--- | :--- |
| Code du Travail (مدونة الشغل) | `مدونة الشغل-2-106.pdf` | `travail` | Contrats de travail (CDD/CDI), licenciement abusif, indemnites legales, preavis, litiges sociaux, securite au travail. |
| Code de la Famille (مدونة الأسرة) | `مدونة الأسرة-9-87.pdf` | `famille` | Fiançailles, mariage, divorce judiciaire, pensions alimentaires (nafaqa), garde des enfants (hadana), successions et tutelles. |
| Dahir des Obligations et Contrats (قانون الالتزامات والعقود - D.O.C) | `قانون الالتزامات والعقود-5-258.pdf` | `civil` | Droit commun des contrats, obligations civiles, nullites, responsabilites delictuelle et contractuelle, clauses resolutoires. |
| Code de Commerce (مدونة التجارة) | `مدونة-التجارة-4-174.pdf` | `commerce` | Actes de commerce, statut du commerçant, effets de commerce (lettre de change, cheque), fonds de commerce, difficultes de l'entreprise. |
| Code de Procedure Civile (قانون المسطرة المدنية) | `قانون_المسطرة_المدنية_(المغرب)-5-128.pdf` | `procedure_civile` | Competence territoriale et d'attribution, assignations, delais de recours (appel, cassation), execution des jugements civils. |
| Code de Procedure Penale (قانون المسطرة الجنائية) | `الجنائية المسطرة -25-314.pdf` | `procedure_penale` | Enquete preliminaire, garde a vue, droits de la defense, instruction preparatoire, juridictions de jugement et mandats de justice. |

---

## Architecture logicielle et arborescence

```
c:\Users\dell\Desktop\LOI\
|
+-- backend\
|   +-- agent\                         # Package d'orchestration LangGraph
|   |   +-- __init__.py                # Export du graphe compile
|   |   +-- graph.py                   # Definition du StateGraph et arêtes conditionnelles
|   |   +-- nodes.py                   # Implementation des 5 nœuds d'execution et 2 nœuds de securite
|   |   +-- state.py                   # Typage d'etat (TypedDict) et modeles Pydantic
|   |   +-- tools.py                   # Utilitaires complementaires
|   |
|   +-- chroma_db\                     # Persistance du Vector Store ChromaDB
|   |   +-- chroma.sqlite3             # Base de donnees relationnelle de metadonnees
|   |   +-- [uuid]\                    # Index vectoriels HNSW (data_level0.bin, header.bin...)
|   |
|   +-- PDFs\                          # Documents officiels sources
|   |   +-- مدونة الشغل-2-106.pdf
|   |   +-- مدونة الأسرة-9-87.pdf
|   |   +-- مدونة-التجارة-4-174.pdf
|   |   +-- قانون الالتزامات والعقود-5-258.pdf
|   |   +-- قانون_المسطرة_المدنية_(المغرب)-5-128.pdf
|   |   +-- الجنائية المسطرة -25-314.pdf
|   |
|   +-- .env                           # Configuration d'environnement et cles API
|   +-- .gitignore                     # Exclusions Git
|   +-- app.py                         # Application serveur FastAPI
|   +-- bm25_index.pkl                 # Index lexical BM25 serialise
|   +-- chunks.json                    # Corpus extrait et deduplique (4 204 articles)
|   +-- indexer.py                     # Script de generation des index ChromaDB et BM25
|   +-- ingest.py                      # Script ETL de parsing des PDFs sources
|   +-- list_models.py                 # Utilitaire de diagnostic des modeles Gemini
|   +-- main.py                        # Script d'execution CLI et tests de graphe multi-tours
|   +-- parser.py                      # Moteur d'extraction regex et normalisation arabe
|   +-- retriever.py                   # Classe HybridLegalRetriever (RRF)
|   +-- schema.py                      # Modele LegalChunk
|   +-- test_embed.py                  # Script de test de l'embedding BGE-M3 local
|   +-- test_ls.py                     # Script de verification de la connexion LangSmith
|
+-- Frontend\
|   +-- public\                        # Fichiers statiques web
|   +-- src\
|   |   +-- assets\                    # Ressources graphiques (logos, illustrations)
|   |   +-- components\                # Composants d'interface React
|   |   |   +-- ChatInput.jsx          # Champ de saisie avec gestion de soumission multilingue
|   |   |   +-- ChatMessage.jsx        # Affichage du message, badges d'audit, boutons sources
|   |   |   +-- LegalDrawer.jsx        # Tiroir lateral pour lecture des articles officiels RTL
|   |   +-- services\
|   |   |   +-- api.js                 # Client HTTP Axios vers l'API Backend
|   |   +-- store\
|   |   |   +-- useChatStore.js        # Gestionnaire d'etat global Zustand
|   |   +-- App.jsx                    # Structure de page, barre laterale et conteneur principal
|   |   +-- App.css                    # Styles specifiques
|   |   +-- index.css                  # Feuilles de style Tailwind CSS v4
|   |   +-- main.jsx                   # Point d'entree de l'application React
|   |
|   +-- package.json                   # Dependances npm et scripts de build
|   +-- vite.config.js                 # Configuration du bundler Vite
|
+-- README.md                          # Documentation technique de reference
```

---

## Specifications de l'API Backend (FastAPI)

Le serveur backend expose une API REST documentee interactivement via Swagger UI (`/docs`).

### Point de terminaison 1 : Verification de sante
- Methode : `GET`
- Route : `/`
- Reponse 200 :
```json
{
  "status": "healthy",
  "service": "Moroccan Legal Agent API",
  "version": "1.0.0"
}
```

### Point de terminaison 2 : Consultation juridique interactive
- Methode : `POST`
- Route : `/api/chat`
- Entete : `Content-Type: application/json`

#### Corps de requete (`ChatRequest`)
```json
{
  "message": "J'ai ete licencie abusivement apres 3 ans de travail sans preavis.",
  "thread_id": "session-unique-optionnelle"
}
```

#### Corps de reponse (`ChatResponse`)
```json
{
  "thread_id": "session-unique-optionnelle",
  "answer": "En vertu des dispositions de la Loi n° 65-99 formant Code du Travail, notamment les articles 39, 41 et 51...",
  "target_category": "travail",
  "verification_status": "pass",
  "cited_articles": ["39", "41", "51"],
  "context_articles": ["المادة 39", "المادة 41", "المادة 51", "المادة 52"],
  "documents": [
    {
      "source": "مدونة الشغل",
      "article_no": "المادة 39",
      "text": "[مدونة الشغل | المادة 39]\nتعتبر بمثابة أخطاء جسيمة يمكن أن تؤدي إلى الفصل..."
    }
  ]
}
```

---

## Architecture Frontend (React & Zustand)

L'application web client est conçue pour repondre aux exigences des interfaces de consultation d'aide a la decision :

### 1. Gestion de l'etat global (`useChatStore`)
Le store Zustand assure la centralisation des etats metiers :
- `messages` : Tableau historique horodate comprenant l'auteur (`user` ou `assistant`), le contenu, les articles sources et les metadonnees d'audit.
- `threadId` : Cle de session conservee tout au long de la conversation pour maintenir la coherence multi-tours cote LangGraph.
- `isLoading` : Indicateur d'activite bloquant la multi-soumission lors du passage dans le graphe.
- `selectedDocument` : Document source actif, projete dans le panneau d'inspection lateral.

### 2. Composant de consultation textuelle (`LegalDrawer`)
Permet d'afficher instantanement le texte original arabe d'un article cite en cliquant sur le badge correspondant sous la reponse. Le panneau applique un rendu typographique avec orientation droite-a-gauche (`dir="rtl"`), garantissant une lecture fidele du texte juridique authentique.

### 3. Indication du niveau de confiance
Chaque reponse de l'assistant affiche un badge dedie :
- "Audite & Conforme" (fond vert emeaude) : Indique une validation formelle par le double niveau du juge.
- "Reserve Juridique" (fond ambre) : Signale une consultation ayant atteint la limite des tentatives ou presentant des reserves explicites.

---

## Observabilite et tracabilite (LangSmith)

Le systeme integre une telemetrie complete via LangSmith, configurable dans le fichier `.env` :

```env
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_API_KEY=votre_cle_langsmith
LANGSMITH_PROJECT=legal-rag-maroc
```

Cette integration permet d'auditer en continu :
- La latence d'execution de chaque nœud du StateGraph.
- Le taux de passage au premier tour vs le taux d'activation des boucles correctives.
- Les motifs exacts des sanctions emises par l'AI Judge (divergences de numerotation ou derives semantiques).
- La consommation precise de tokens par requete et par session.

---

## Guide d'installation et de deploiement

### Pre-requis systeme
- Systeme d'exploitation : Windows, Linux, ou macOS.
- Python : Version 3.10 ou superieure.
- Node.js : Version 18.0.0 ou superieure avec npm.
- Ollama : Installe et operationnel pour la generation locale des embeddings.

### Etape 1 : Configuration du modele d'embedding local (Ollama)
Ouvrir un terminal et telecharger le modele multilingual BGE-M3 :

```bash
ollama pull bge-m3
```

Verifier le fonctionnement avec la commande :
```bash
ollama run bge-m3 "اختبار التضمين"
```

### Etape 2 : Configuration du Backend
1. Naviguer dans le repertoire backend :
```bash
cd backend
```

2. Creer un environnement virtuel Python et l'activer :
- Sur Windows (PowerShell) :
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
- Sur Linux/macOS :
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Installer les dependances Python requises :
```bash
pip install -r requirements.txt
```

4. Configurer les variables d'environnement dans un fichier `.env` a la racine du dossier `backend` :
```env
GEMINI_API_KEY=votre_cle_api_google_gemini
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_API_KEY=votre_cle_langsmith
LANGSMITH_PROJECT=qanoon-ai
```

### Etape 3 : Initialisation et verification de la base de donnees
Si les fichiers `chunks.json`, `bm25_index.pkl` et le dossier `chroma_db` sont deja presents dans `backend/`, l'etape d'indexation peut etre ignoree. Pour reconstruire entierement les index a partir des PDFs :

1. Extraction des articles de loi depuis les PDFs :
```bash
python ingest.py
```
2. Vectorisation et indexation hybride :
```bash
python indexer.py
```

### Etape 4 : Lancement du serveur API Backend
Depuis le dossier `backend` avec l'environnement virtuel actif :
```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
Le serveur repond sur `http://127.0.0.1:8000`. La documentation Swagger est disponible sur `http://127.0.0.1:8000/docs`.

### Etape 5 : Installation et demarrage du Frontend
1. Ouvrir un second terminal et naviguer vers le dossier Frontend :
```bash
cd Frontend
```

2. Installer les packages npm :
```bash
npm install
```

3. Lancer le serveur de developpement Vite :
```bash
npm run dev
```
L'interface utilisateur est alors accessible a l'adresse `http://localhost:5173`.

---

## Guide d'utilisation et scenarios

### Scenario 1 : Question relative au droit du travail (Multi-tours avec memoire)
- Tour 1 (Utilisateur) :
  *"J'ai ete licencie apres 3 annees de travail sans motif et sans préavis. Que puis-je reclamer ?"*
  - Comportement : Extraction des faits (licenciement sans preavis, 3 ans d'anciennete). Routage vers la categorie `travail`. Extraction des articles 39, 41 et 51 de la Moudawana du travail. Synthese chiffree des droits a indemnite de preavis, indemnite de licenciement et dommages-interets.
- Tour 2 (Utilisateur) :
  *"Et quel est le delai pour porter l'affaire devant le tribunal ?"*
  - Comportement : Le systeme reformule la question en intégrant le contexte precedent (*"Delai de prescription de l'action en justice pour licenciement abusif selon le code du travail marocain"*). Extraction de l'article 65 fixant le delai de prescription a 90 jours.

### Scenario 2 : Demande d'information sans precision factuelle
- Utilisateur :
  *"Bonjour, j'ai besoin d'une aide juridique."*
  - Comportement : Le nœud `update_case` qualifie `is_missing_info: True`. Routage vers le nœud `clarify` sans declencher inutilement de recherche hybride. L'assistant demande la nature de la situation contractuelle ou du litige.

### Scenario 3 : Audit d'une tentative d'hallucination de reference
Si le generateur cite accidentellement un numero d'article inexistant ou ne figurant pas dans les 4 articles sources du contexte, le niveau 1 de l'AI Judge intercepte l'anomalie en temps reel et force la regeneration instantanee avec une instruction prohibitive explicite avant l'envoi de la reponse a l'utilisateur.

---

## Avertissement legal (Legal Disclaimer)

Qanoon AI est un systeme d'assistance et de recherche documentaire base sur l'intelligence artificielle. Les syntheses, interpretations et orientations fournies le sont a titre purement informatif et pedagogique. Elles ne sauraient en aucun cas se substituer a la consultation formelle d'un avocat inscrit au barreau, d'un notaire, d'un huissier de justice ou de toute autre autorite judiciaire habilitee. L'utilisation des analyses produites par ce systeme s'effectue sous l'entiere responsabilite de l'utilisateur.
