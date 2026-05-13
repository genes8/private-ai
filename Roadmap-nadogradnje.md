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

## **Kako bi se uklopio u tvoju arhitekturu**

Umesto ovoga:

API → Jaeger

ja bih za AI aplikaciju stavio:

API / LangGraph → Langfuse  
Dokploy → infrastruktura

Praktično:

React SPA  
  ↓  
FastAPI  
  ↓  
LangGraph Pipeline  
  ↓  
Retriever / Reranker / Ollama  
  ↓  
Langfuse traces

## **Šta bi Langfuse hvatao kod tebe**

Na primer za jedan `/chat` request:

Trace: user pita pitanje

Span 1: auth/user/session  
Span 2: query preprocessing  
Span 3: hybrid retrieval  
Span 4: Qdrant search  
Span 5: reranking  
Span 6: prompt building  
Span 7: Ollama LLM call  
Span 8: final response  
Span 9: evaluation / score

I za svaki korak vidiš:

koliko je trajao  
šta je bio input  
šta je bio output  
koji model je korišćen  
koliko tokena  
gde je puklo  
koliko je koštalo  
koji user/session

Langfuse podržava traces, session tracking, custom trace IDs, token/cost tracking i latency monitoring za LLM aplikacije.

## **Da li menja Observability Router?**

Ne potpuno.

Ja bih ostavio minimalni `Observability Router`, ali ga pojednostavio.

### **Backend i dalje treba da ima:**

GET /health  
GET /ready  
GET /metrics

Zbog:

Dokploy health check  
Docker healthcheck  
load balancer readiness  
uptime monitoring  
basic Prometheus metrics

### **Langfuse bi preuzeo:**

/traces  
LLM latency  
agent pipeline debugging  
prompt/output logs  
retrieval debug  
evaluation scores  
chat session analysis

Znači ne bih pravio veliki custom `/traces` sistem ako koristiš Langfuse.

## **Najbolja kombinacija za tebe**

Dokploy  
\- deployment  
\- logs  
\- service status  
\- CPU/RAM/disk/network

FastAPI Observability Router  
\- /health  
\- /ready  
\- /metrics  
\- basic service checks

Langfuse  
\- LLM traces  
\- LangGraph steps  
\- prompts  
\- outputs  
\- latency per step  
\- token/cost tracking  
\- evals  
\- datasets

## **Zaključak**

Za tvoj stack:

React \+ FastAPI \+ LangGraph \+ HybridRetriever \+ Qdrant \+ Ollama

**Langfuse je odličan izbor.**

Posebno zato što radi dobro za:

AI chat aplikacije  
RAG sisteme  
agente  
LangGraph pipeline  
local LLM / Ollama setup  
debugging promptova  
evaluaciju kvaliteta odgovora

Ja bih arhitekturu promenio ovako:

API \--\> Observability Router  
API \--\> LangGraph  
LangGraph \--\> Retriever  
LangGraph \--\> Reranker  
LangGraph \--\> Ollama  
LangGraph \--\> Langfuse  
API \--\> Langfuse  
Dokploy \--\> API / DB / Qdrant / Ollama / Langfuse

Odnosno:

**Dokploy za deploy i infra monitoring.**  
 **Langfuse za AI observability.**  
 **Mali FastAPI Observability Router samo za health/metrics.**

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

