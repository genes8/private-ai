# site-copy vs. aplikacija — gap analiza

Datum: 2026-05-27

Upoređivanje svega što `site-copy.md` obećava sa trenutnom implementacijom u `safe4ai-pilot/`.

---

## KRITIČNO

### 1. Output Guard ne proverava citate

- **site-copy:** "The output guard rejects responses without at least one citation" + "≥ 1 required citation"
- **trenutno:** `output_filter.py` proverava samo PII halucinaciju i dužinu (4000 chars warning). Nema nikakve logike za citation presence check.
- **fajl:** `safe4ai-pilot/app/security/output_filter.py`
- **šta treba:** Dodati citation presence check — ako odgovor nema bar jedan citation (npr. `[1]` format), vratiti `GuardResult(allowed=False, reason="Response missing required citation")`.

### 2. Output Guard dužina: 1024 tokena vs. 4000 karaktera

- **site-copy:** "max length 1024 tokens"
- **trenutno:** `_LONG_ANSWER_THRESHOLD = 4000` chars, i to samo kao `logger.warning` (ne blokira).
- **fajl:** `safe4ai-pilot/app/security/output_filter.py:12`
- **šta treba:** Promeniti threshold na ~1024 tokena (~4096 chars kao aprox). Pretvoriti iz warning u hard block (`GuardResult(allowed=False)`).

### 3. Audit archive to immutable storage ne postoji

- **site-copy:** "∞ archived to immutable storage"
- **trenutno:** `audit_cleanup.py` samo briše stare redove iz Postgres-a. Nema nikakav mehanizam za arhiviranje pre brisanja.
- **fajl:** `safe4ai-pilot/scripts/audit_cleanup.py`
- **šta treba:** Pre brisanja, arhivirati redove u immutable storage (S3 Glacier / S3 Object Lock / lokalni WORM filesystem). Dodati konfiguraciju za archive destination.

### 4. Signed / tamper-evident CSV export ne postoji

- **site-copy:** "CSV exportable, signed, tamper-evident"
- **trenutno:** CSV export postoji u admin ActivityPage, ali nema digitalno potpisivanje niti hash chain.
- **fajl:** `safe4ai-pilot/app/api/audit_routes.py` (CSV export endpoint)
- **šta treba:** Dodati HMAC-SHA256 potpisivanje CSV fajla (ili pojedinačnih redova). Dodati hash chain gde svaki red sadrži hash prethodnog. Uključiti signature u export metadata.

---

## SREDNJE

### 5. SSO (SAML, OIDC) — samo placeholder

- **site-copy:** "SSO (SAML, OIDC)" u Team tier + "auth · sso · rbac" u pipeline stage meta
- **trenutno:** Postoji `sso_only` toggle u Settings UI (`SettingsPage.tsx:279`), ali nema nikakvu SAML/OIDC integraciju. Toggle samo onemogućava password login.
- **fajlovi:** `safe4ai-pilot/app/services/settings_service.py:57`, `safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx:279`
- **šta treba:** Implementirati SAML2 i/ili OIDC IdP integraciju. Koristiti `pyramid_saml` ili `authlib` za OIDC. Dodati IdP metadata konfiguraciju u Settings.

### 6. Seat / query limit enforcement

- **site-copy:** Evaluation: "up to 5 seats, 5,000 queries/month" · Team: "up to 50 seats, unlimited queries"
- **trenutno:** Nema nikakvog seat limita (invite radi za neograničeno korisnika) niti query quota enforcement-a.
- **fajlovi:** `safe4ai-pilot/app/api/user_routes.py`, `safe4ai-pilot/app/api/chat_routes.py`
- **šta treba:** Dodati `max_seats` i `monthly_query_limit` u app konfiguraciju. Enforce u invite endpoint-u (provera seat count) i chat endpoint-u (provera monthly query count). Dodati tier konfiguraciju.

### 7. Observability export — samo Jaeger

- **site-copy:** "Ship to Jaeger, Tempo, Honeycomb, or your own stack"
- **trenutno:** Hardcoded `OTLPSpanExporter` za Jaeger endpoint. Nema konfiguraciju za druge backend-ove.
- **fajl:** `safe4ai-pilot/observability/tracer.py`
- **šta treba:** Dodati konfigurabilni OTEL exporter endpoint i headers u env vars / settings. Podržati custom endpoint za Tempo, Honeycomb, itd.

### 8. Provider toggle audit log

- **site-copy:** "The provider toggle lives in admin settings, takes effect within 30 seconds, and is itself audited."
- **trenutno:** Provider toggle postoji, ali nije jasno da li se promena provider moda eksplicitno loguje u AuditLog sa posebnim action_type.
- **fajl:** `safe4ai-pilot/app/services/settings_service.py`
- **šta treba:** Dodati eksplicitni AuditLog unos sa `action_type="settings_provider_change"` kada se provider mode promeni. Uključiti old/new vrednost u metadata.

### 9. Input Guard — blocked terms provera kroz Settings UI

- **site-copy:** "Block any prompt mentioning patient identifiers — at the edge, not in the model" + "add blocked terms (mrn, nhs number, ssn) via Settings → Security"
- **trenutno:** Blocked terms logika postoji u content_filter/input_guard. Treba proveriti da li je potpuno konfigurabilna kroz admin Settings UI Security sekciju.
- **fajlovi:** `safe4ai-pilot/app/security/content_filter.py`, `safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx`
- **šta treba:** Verifikovati da Settings → Security sekcija ima polje za dodavanje/brisanje blocked terms i da input_guard koristi te termine u realnom vremenu.

---

## NISKO

### 10. RBAC role se ne poklapaju

- **site-copy:** "Role-based access (admin / pilot_user)"
- **trenutno:** Role su `admin / editor / viewer`
- **fajl:** `safe4ai-pilot/app/db/models.py` (User model)
- **šta treba:** Ili dodati `pilot_user` rolu ili ažurirati site-copy da koristi postojeće role ime. Preporučuje se drugo — `editor` je već adekvatan ekvivalent.

### 11. Controls mapping dokument (SOC 2 / ISO 27001 / NIST 800-53)

- **site-copy FAQ:** "We provide a controls mapping document (SOC 2, ISO 27001, NIST 800-53) that maps every audit field, guard, and span to the relevant control families."
- **trenutno:** Ne postoji
- **šta treba:** Kreirati markdown/PDF dokument koji mapira svaki guard, audit polje i OTEL span na SOC 2, ISO 27001 i NIST 800-53 kontrolne familije.

### 12. Changelog sekcija

- **site-copy Footer:** "changelog" link u Product grupi
- **trenutno:** Ne postoji ni changelog page ni changelog data
- **šta treba:** Dodati changelog route ili bar `CHANGELOG.md` u repo. Može biti statički za sada.

### 13. vLLM podrška

- **site-copy:** "ollama · qwen3 · vllm" meta tag u LLM generate stage
- **trenutno:** Radi sa bilo kojim OpenAI-compatible endpoint-om, ali nema eksplicitnu vLLM konfiguraciju/dokumentaciju
- **šta treba:** Dokumentovati vLLM deployment kao provider opciju. eventualno dodati vLLM-specific health check.

### 14. Status pill ("All systems operational")

- **site-copy Footer:** Status pill "All systems operational" + "indexing healthy · all documents indexed"
- **trenutno:** Health check postoji na login stranici, ali nema status pill nigde u app footer-u
- **šta treba:** Dodati status indikator u app layout sa informacijom o zdravlju sistema i indexing statusu.

---

## MARKETING SITE (landing page)

Ceooo marketing sajt opisan u `site-copy.md` **nije izgrađen**. Nijedna od sekcija ne postoji kao frontend:

1. Navigation (sticky nav, logo, anchor links, mobile drawer)
2. Hero (eyebrow, headline, subhead, CTAs, highlights grid, mock pipeline)
3. Logo Wall (Nordbank, MERIDIAN, Lumen Health, ATLAS / pharma, CIVIC GRID, Halcyon Re)
4. Features (6 capabilities: Audit, Guards, Retrieval, Observability, Grounded, Private)
5. Live Preview / Chat Demo (3 sample questions sa animiranim odgovorima)
6. How It Works (7-stage pipeline sa hover state-ovima, latency bar)
7. Security Guards (3 guarda sa input/output primerima)
8. Audit Trail (stats grid, live ticker, CSV export)
9. Observability (trace vizualizacija, Python code sample)
10. Use Cases (Marta / Daniel / Aisha persone sa flow-ovima)
11. Comparison (8-row tabela vs. cloud LLM)
12. Testimonials (3 quotes)
13. Pricing (3 tier-a: Evaluation / Team / Enterprise)
14. FAQ (8 pitanja)
15. CTA forma (email + formsubmit.co)
16. Footer (tagline, status pill, link grupe, legal)

---

## Prioritet za implementaciju

| Redosled | stavka | nivo | procena napora |
|----------|--------|------|----------------|
| 1 | Citation check u output guard | Kritično | Mala |
| 2 | Length bound hard limit | Kritično | Mala |
| 3 | Immutable storage archive za audit | Kritično | Srednja |
| 4 | Signed/tamper-evident CSV | Kritično | Srednja |
| 5 | SAML/OIDC SSO integracija | Srednje | Velika |
| 6 | Seat/query limit enforcement | Srednje | Srednja |
| 7 | Provider change audit log | Srednje | Mala |
| 8 | Configurable OTEL exporter | Nisko | Mala |
| 9 | Blocked terms UI verifikacija | Srednje | Mala |
| 10 | RBAC role alignment | Nisko | Mala |
| 11 | Controls mapping dokument | Nisko | Srednja |
| 12 | Changelog | Nisko | Mala |
| 13 | vLLM dokumentacija | Nisko | Mala |
| 14 | Status pill | Nisko | Mala |
