# TRENUTNO STANJE ARHITWEKTURE

Ovo je arhitektura za **AI chat/RAG aplikaciju**: frontend šalje zahteve backendu, backend proverava korisnika, vodi chat logiku, pretražuje dokumente, šalje kontekst LLM-u i vraća odgovor korisniku.

graph TB  
Frontend → Backend → LangGraph/Retriever/Reranker → Qdrant/Ollama  
Backend → PostgreSQL  
Backend → Jaeger

## **1\. Frontend**

### **`React SPA`**

**SPA \= Single Page Application**

To je web aplikacija u Reactu koju korisnik vidi u browseru.

Radi stvari kao:

* login/register forma  
* chat interfejs  
* admin panel  
* prikaz dokumenata  
* prikaz odgovora od AI-ja  
* slanje poruka backendu preko API-ja

Frontend ne radi AI logiku. On samo prikazuje UI i komunicira sa backendom.

### **`Protected Routes`**

To znači da određene stranice nisu dostupne dok korisnik nije ulogovan.

Na primer:

* `/login` — javno  
* `/chat` — samo ulogovan korisnik  
* `/admin` — samo admin korisnik  
* `/observability` — možda samo admin/dev korisnik

Frontend obično proverava da li postoji JWT token ili session.

---

# **2\. Backend**

## **`FastAPI App`**

Ovo je glavni backend server.

On prima sve zahteve sa frontenda:

* login  
* slanje chat poruke  
* upload dokumenata  
* admin akcije  
* monitoring/logging zahteve

FastAPI je ulazna tačka sistema.

Primer:

React šalje poruku → FastAPI primi zahtev → pokrene AI pipeline → vrati odgovor

---

## **`Auth Router`**

Deo backenda koji se bavi autentifikacijom.

Radi:

* login  
* register  
* logout  
* refresh token  
* provera JWT tokena  
* role-based access control

Na primer:

Korisnik unese email/password  
→ Auth Router proveri podatke  
→ vrati access token

---

## **`Chat Router`**

Deo backenda koji upravlja chat funkcionalnošću.

Radi:

* prima korisničko pitanje  
* proverava da li korisnik ima pravo pristupa  
* šalje pitanje u LangGraph pipeline  
* vraća AI odgovor  
* čuva chat istoriju u bazi

Primer flow:

User: "Šta piše u dokumentu?"  
→ Chat Router  
→ LangGraph Pipeline  
→ Retriever  
→ Ollama  
→ odgovor nazad korisniku

---

## **`Admin Router`**

Deo backenda za administratorske funkcije.

Može da radi:

* upravljanje korisnicima  
* upload dokumenata  
* brisanje dokumenata  
* pregled svih chatova  
* podešavanje modela  
* podešavanje RAG izvora  
* upravljanje permisijama

Na primer admin može da ubaci nove dokumente koje će AI kasnije koristiti za odgovore.

---

## **`Observability Router`**

Deo backenda za monitoring i debugging.

Radi stvari kao:

* health check  
* status servisa  
* logs  
* metrics  
* traces  
* latency pregled  
* greške u pipeline-u

Primer endpointa:

GET /health  
GET /metrics  
GET /traces

Koristi se da znaš da li sistem radi normalno.

---

## **`PostgreSQL + pgvector`**

Glavna relaciona baza.

Čuva:

* korisnike  
* role  
* chat istoriju  
* dokumente/metapodatke  
* sesije  
* audit logove  
* konfiguracije

`pgvector` je ekstenzija za čuvanje vektora/embeddinga u PostgreSQL-u.

Međutim, u tvojoj arhitekturi postoji i `Qdrant`, tako da PostgreSQL verovatno čuva aplikacione podatke, dok Qdrant služi kao glavni vector store.

Moguće podele:

PostgreSQL:  
\- users  
\- conversations  
\- messages  
\- documents metadata  
\- permissions

Qdrant:  
\- document chunks  
\- embeddings  
\- semantic search

---

## **`LangGraph Pipeline`**

Ovo je srce AI logike.

LangGraph definiše tok kroz koji pitanje prolazi.

Na primer:

1\. primi pitanje  
2\. proveri intent  
3\. pronađi relevantne dokumente  
4\. rerankuj rezultate  
5\. napravi prompt  
6\. pozovi LLM  
7\. proveri odgovor  
8\. vrati finalni odgovor

LangGraph je dobar kada želiš kontrolisan, višekoračni AI agent/pipeline, a ne samo običan jedan LLM poziv.

Primer:

User question  
→ Retrieve documents  
→ Rerank documents  
→ Generate answer  
→ Save result

---

## **`HybridRetriever`**

Retriever je komponenta koja pronalazi relevantan kontekst za pitanje.

`Hybrid` znači da verovatno kombinuje više metoda pretrage:

1. **semantic search** — traži po značenju preko embeddinga  
2. **keyword search** — traži po ključnim rečima  
3. možda **metadata filtering** — traži samo dokumente određenog korisnika, projekta, tipa itd.

Primer:

Korisnik pita:

"What is the refund policy?"

Retriever traži delove dokumenata koji pričaju o refund policy, čak i ako ne koriste baš iste reči.

---

## **`Reranker`**

Reranker uzima rezultate koje je Retriever našao i ponovo ih sortira po relevantnosti.

Zašto je potreban?

Retriever može da pronađe 20 potencijalno korisnih chunkova, ali nisu svi jednako dobri.

Reranker bira najbolje.

Primer:

Retriever pronađe 20 rezultata  
→ Reranker ih rangira  
→ top 5 ide u LLM prompt

Bez rerankera, LLM može dobiti slabiji ili nebitan kontekst.

---

# **3\. External Services**

## **`Qdrant Vector Store`**

Qdrant je specijalizovana vector baza.

Čuva:

* embeddinge dokumenata  
* chunkove dokumenata  
* metadata  
* vektorsku pretragu

Koristi se za RAG.

Flow:

Dokument se podeli na chunkove  
→ svaki chunk dobije embedding  
→ embedding se čuva u Qdrant  
→ korisničko pitanje se pretvori u embedding  
→ Qdrant vraća najbliže chunkove

---

## **`Ollama LLM`**

Ollama služi za lokalno pokretanje LLM modela.

Na primer:

* Llama  
* Mistral  
* Qwen  
* DeepSeek  
* Gemma

U ovoj arhitekturi Ollama se koristi za dve stvari:

### **1\. Generisanje odgovora**

LangGraph → Ollama → finalni AI odgovor

### **2\. Embedding / pomoćna obrada**

Pošto `Retriever --> Ollama`, moguće je da Ollama generiše embeddinge ili radi query transformation.

Na primer:

Korisničko pitanje → Ollama embedding model → Qdrant search

---

## **`Jaeger UI`**

Jaeger je alat za tracing.

Koristi se da vidiš šta se desilo unutar jednog zahteva.

Na primer, korisnik pošalje pitanje, a ti vidiš:

Request received: 20ms  
Auth check: 10ms  
Retriever: 300ms  
Reranker: 500ms  
LLM call: 4.2s  
DB save: 50ms  
Total: 5.1s

Ovo je jako korisno za debugging i optimizaciju.

Ako chat sporo odgovara, Jaeger ti pokaže gde je usko grlo.

---

# **Kako ceo sistem radi zajedno**

Tipičan flow za jedno pitanje:

1\. Korisnik otvori React aplikaciju  
2\. Loginuje se  
3\. React čuva auth token  
4\. Korisnik pošalje pitanje  
5\. FastAPI primi zahtev  
6\. Auth Router proveri token  
7\. Chat Router prosledi pitanje u LangGraph  
8\. LangGraph pozove HybridRetriever  
9\. HybridRetriever koristi Qdrant i/ili Ollama  
10\. Qdrant vrati relevantne dokumente  
11\. Reranker sortira najbolje rezultate  
12\. LangGraph napravi prompt sa kontekstom  
13\. Ollama generiše odgovor  
14\. Backend snimi poruku u PostgreSQL  
15\. React prikaže odgovor korisniku  
16\. Jaeger beleži trag celog procesa

---

# **Najkraće rečeno**

Ovo je modularna AI aplikacija:

| Komponenta | Uloga |
| ----- | ----- |
| React SPA | Korisnički interfejs |
| Protected Routes | Štiti stranice od neulogovanih korisnika |
| FastAPI | Glavni backend |
| Auth Router | Login, tokeni, korisnici |
| Chat Router | Chat endpointi |
| Admin Router | Admin funkcije |
| Observability Router | Monitoring i health checks |
| PostgreSQL | Glavna baza aplikacije |
| pgvector | Vektori u Postgresu, ako se koriste |
| LangGraph | AI workflow/pipeline |
| HybridRetriever | Pronalazi relevantne dokumente |
| Reranker | Bira najbolje rezultate |
| Qdrant | Vector baza za RAG |
| Ollama | Lokalni LLM |
| Jaeger | Tracing/debugging |

Ovo je dobra arhitektura za **on-premise private AI chatbot / RAG sistem** gde podaci ostaju na tvojoj infrastrukturi.

#    NADOGRADNJA ARCHITECTURE

Za **produkciju** bih stavio **sva tri**, ali sa jasnom podelom da se ne duplira posao.

Dokploy \= deployment \+ infra status  
Langfuse \= AI/LLM observability  
Jaeger \= distributed tracing / backend tracing

## **Produkcijska preporuka**

### **1\. Dokploy — obavezno**

Koristi ga za:

deploy aplikacija  
restart/redeploy  
env vars  
container logs  
CPU/RAM/disk/network  
status servisa  
Docker/Compose management

On ti je **platform layer**.

---

### **2\. Langfuse — obavezno za AI app**

Koristi ga za:

LLM traces  
LangGraph node traces  
prompt input/output  
retrieval debugging  
token usage  
cost tracking  
user sessions  
feedback/evaluations  
debugging loših odgovora

On ti je **AI observability layer**.

---

### **3\. Jaeger — preporučljivo za produkciju**

Koristi ga za:

API request tracing  
DB latency  
Qdrant latency  
Ollama/LLM service latency  
worker latency  
network bottlenecks  
distributed trace kroz više servisa

On ti je **backend/infrastructure tracing layer**.

---

## **Kako bih ja to složio**

React SPA  
   ↓  
FastAPI API  
   ↓  
LangGraph Pipeline  
   ↓  
Retriever / Reranker / Qdrant / Ollama

Observability:

FastAPI / LangGraph → Langfuse  
FastAPI / services → OpenTelemetry → Jaeger  
Dokploy → containers / deploy / infra metrics / logs

## **Minimalni produkcijski setup**

U produkciji bih imao:

dokploy  
postgres  
qdrant  
ollama  
fastapi-api  
frontend  
langfuse  
jaeger  
otel-collector

Još bolje ako dodaš:

prometheus  
grafana

Ali ako hoćeš da ne preteraš u startu, onda:

Dokploy \+ Langfuse \+ Jaeger \+ OpenTelemetry Collector

je sasvim dovoljno.

---

## **Šta da ostane u Observability Router-u**

Ne pravi veliki custom observability sistem.

Ostavi samo:

GET /health  
GET /ready  
GET /metrics  
GET /version

A ovo prebaci na alate:

/traces → Jaeger \+ Langfuse  
/logs → Dokploy / kasnije Loki  
LLM traces → Langfuse  
latency traces → Jaeger  
infra status → Dokploy

## **Finalna odluka**

Za **produkciju**:

DA — Dokploy  
DA — Langfuse  
DA — Jaeger  
DA — minimalni FastAPI Observability Router

Ne zato što rade isto, nego zato što pokrivaju različite slojeve:

Dokploy: da li sistem radi  
Jaeger: gde je request usporio/pukao  
Langfuse: zašto je AI dao loš/spor/skup odgovor

To je najzdravija produkcijska kombinacija za tvoj stack.

**PODESAVANJE LLM-a**

Evo šta vidim iz koda:

\*\*Trenutno stanje:\*\*  
\- \`OLLAMA\_MODEL=qwen3.5:9b\` — \~5.5GB download, \~9GB RAM za CPU inferenciju  
\- \`qwen2.5vl:7b\` (OCR) — \~4.7GB  
\- Docker Compose pokreće Ollama container \+ \`ollama-init\` koji pokušava pull-ovati oba modela pri \`docker compose up\`  
\- Već imaš native Ollama na macOS (\`ollama list\` radi), ali model nije pulled  
\- \`qwen3-coder:30b\` (18GB) je jedini veliki model — nepotreban za ovaj app

\---

\#\# Predlog: Dva režima rada

\#\#\# 1\. \*\*Local Dev (preporučeno za testiranje)\*\* — Ollama na host-u, app lokalno

Najjednostavniji i najbrži pristup. Ne treba ti Ollama u Docker-u uopšte.


\# 2\. Embedding model već imaš  
ollama pull nomic-embed-text     \# već pulled

\# 3\. OCR \- skip za sad (koristi fallback bez OCR-a)  
\# Ako treba: ollama pull minicpm-v:1b  (\~700MB, minimal vision)


\`\`\`

\*\*Docker Compose\*\* — izbaci Ollama servise, zadrži samo Postgres i Qdrant:  
\`\`\`bash  
docker compose up postgres qdrant jaeger  \# samo infra  
\`\`\`


\---

\#\#\# 2\. \*\*Full Docker\*\* — ako mora sve u kontejnerima

Ollama container mora da pristupa host Ollama-i ili da ima dovoljno RAM-a. Na macOS, Docker Desktop ima limited RAM (default 4GB).

\*\*Rešenje:\*\* Ollama na hostu, app container se konektuje preko \`host.docker.internal\`:

\`\`\`yaml  
\# docker-compose.override.yml  
services:  
  app:  
    environment:  
      \- OLLAMA\_URL=http://host.docker.internal:11434  
  \# Ukloni ollama i ollama-init servise  
\`\`\`

\---

\#\#\# Model-upustvo po RAM kapacitetu

| Model | Download | RAM (CPU) | Kvalitet | Preporuka |  
|-------|----------|-----------|----------|-----------|  
| \`qwen2.5:0.5b\` | 395MB | \~1GB | Low | Samo smoke test |  
| \*\*\`qwen2.5:1.5b\`\*\* | \*\*987MB\*\* | \*\*\~2.5GB\*\* | \*\*Acceptable\*\* | \*\*Najbolji za CPU test\*\* |  
| \`qwen2.5:3b\` | 2GB | \~4.5GB | Good | Ako imaš RAM |  
| \`qwen3.5:9b\` | 5.5GB | \~9GB | Great | Samo sa GPU |  
| \`nomic-embed-text\` | 274MB | \~0.5GB | N/A | Već pulled |  
| \`minicpm-v:1b\` | 700MB | \~1.5GB | Low OCR | Za OCR test |

\---

\#\#\# Šta treba promeniti u kodu

Samo \*\*\`.env\`\*\* — jedina promena je \`OLLAMA\_MODEL\`. Arhitektura već podržava runtime config iz DB (\`runtime\_config.py\` čita \`generation\_model\` iz \`app\_config\` tabele), tako da će Settings page moći da menja model bez restarta.

Za \`docker-compose.yml\`, predlažem da se \`ollama\` i \`ollama-init\` servisi prebace u \*\*opcionu sekciju\*\* ili \`profile\`:

\`\`\`yaml  
\# docker-compose.yml — dodaj profile na ollama servise  
  ollama:  
    profiles: \["with-ollama"\]  \# ne pokreće se podrazumevano  
    ...  
  ollama-init:  
    profiles: \["with-ollama"\]  
    ...  
\`\`\`

Tako \`docker compose up\` pokreće samo infra (postgres, qdrant, jaeger), a \`docker compose \--profile with-ollama up\` pokreće i Ollama u containeru za one kojima treba.

\---

\*\*Moj preporučeni plan za sada:\*\*  
1\. \`ollama pull qwen2.5:1.5b\` — manji model za CPU  
2\. Promeni \`.env\` → \`OLLAMA\_MODEL=qwen2.5:1.5b\`  
3\. Dodaj \`profiles: \["with-ollama"\]\` na Ollama servise u \`docker-compose.yml\`  
4\. Pokreni infra: \`docker compose up postgres qdrant jaeger\`  
5\. Pokreni app lokalno: \`uvicorn app.main:app \--reload\`  
6\. Ollama radi natively na \`localhost:11434\`

Želiš da implementiram ovo?

# DODAVANJE FEATURES

**Šta bi dodao tvojoj aplikaciji da bude bliža ovome**

Prioritetno:

1. **Document ingestion pipeline**  
   * upload PDF/DOCX/XLSX/CSV  
   * OCR ako je skenirano  
   * metadata extraction  
   * tenant/client/project tagging  
2. **RAG workspace**  
   * Qdrant ili pgvector  
   * embeddings  
   * chunking  
   * document citations  
   * source references u odgovorima  
3. **Role-based access**  
   * admin  
   * reviewer  
   * staff  
   * client/project-level access  
4. **Audit log**  
   * ko je pitao  
   * šta je pitao  
   * koji dokumenti su korišćeni  
   * koji odgovor je generisan  
   * kada je eksportovano/sent  
5. **n8n ili workflow engine**  
   * kada dokument stigne → obradi → indeksiraj → obavesti usera  
   * ako fali informacija → kreiraj task  
   * ako je confidence nizak → pošalji na review  
6. **Vertikalni template**  
   * accounting  
   * legal  
   * healthcare  
   * insurance  
   * banking/risk

