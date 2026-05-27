# Product readiness audit: site copy vs aplikacija

Datum: 2026-05-27

Ovaj dokument poredi `site-copy.md`, postojeću `site-copy-gap-analysis.md` i trenutno stanje aplikacije u `safe4ai-pilot/`. Cilj nije "dodaj sve sa sajta", nego odluka šta mora da se izgradi da bi ponuda bila iskrena prema tržištu, šta je validan enterprise roadmap, a šta je marketing copy koji treba spustiti ili dokazati.

## Zaključak

Trenutna aplikacija je blizu korisnog privatnog RAG pilota, ali nije spremna da iskreno podrži sve što website prodaje kroz `Evaluation`, `Team` i `Enterprise` tier. Najveći problem nije širina feature-a, nego razlika između komercijalnih obećanja i hard enforcement-a u aplikaciji.

Najvažnije:

- `Evaluation` se može dovesti do market-ready stanja relativno brzo, ali mora imati seat/query enforcement, jasnu evaluacionu konfiguraciju i istinit audit/citation story.
- `Team` trenutno ne sme da obećava pravi SAML/OIDC SSO dok postoji samo `ssoOnly` toggle.
- `Enterprise` obećanja kao tamper-evident archive, custom retention, air-gap packaging i multi-tenant deployment treba tretirati kao enterprise roadmap, ne kao već postojeći product.
- Fake logos/testimonials/precizne metrike bez dokaza su marketing BS i treba ih ukloniti ili zameniti "example scenario" copy-jem.

## Evidence snapshot

| Area | Website claim | Trenutno stanje | Evidence |
|---|---|---|---|
| Pricing tiers | Evaluation: 5 seats, 5,000 queries/month; Team: 50 seats, SSO, 90d retention; Enterprise: custom archive/policies | Tiers postoje u copy-ju, ali app nema tier config/enforcement | `site-copy.md:106-111`, `safe4ai-pilot/app/api/user_routes.py:66-88`, `safe4ai-pilot/app/api/chat_routes.py:128-142` |
| RBAC | `admin / pilot_user` | Ovo je OK; stara gap analiza je ovde netačna | `site-copy.md:48`, `site-copy-gap-analysis.md:82-87`, `safe4ai-pilot/app/db/models.py:21-23` |
| Output guard citations | Output guard odbija odgovor bez citata | Nije implementirano; proverava PII i samo warning za dužinu | `site-copy.md:53-64`, `site-copy.md:121`, `safe4ai-pilot/app/security/output_filter.py:23-51` |
| Audit CSV | CSV exportable, signed, tamper-evident | CSV export postoji, ali bez potpisa/hash chain-a | `site-copy.md:69`, `safe4ai-pilot/app/api/audit_routes.py:64-122` |
| Immutable archive | 90d retained, archived to immutable storage | Cleanup briše stare redove; nema archive pre brisanja | `site-copy.md:28`, `site-copy.md:69-71`, `safe4ai-pilot/scripts/audit_cleanup.py:35-86` |
| SSO | SSO SAML/OIDC u Team tier-u | Postoji samo `ssoOnly`; nema IdP/OIDC/SAML flow | `site-copy.md:110`, `safe4ai-pilot/frontend/src/pages/admin/SettingsPage.tsx:277-282` |
| Provider modes | local/hybrid/cloud provider toggle | Postoji realna local/hybrid/cloud provider logika | `site-copy.md:116`, `safe4ai-pilot/app/services/provider_settings.py:35-96` |
| Provider toggle audited | Provider toggle je audited | Settings route samo loguje server log; ne kreira `AuditLog` red | `site-copy.md:116`, `safe4ai-pilot/app/api/settings_routes.py:91-111` |
| OTEL | Ship to Jaeger, Tempo, Honeycomb, own stack | OTLP endpoint jeste env-configurable; copy "Jaeger only" nije problem, ali nema UI/docs za backend izbor | `site-copy.md:73-77`, `safe4ai-pilot/observability/tracer.py:27-32` |
| Customer logos/testimonials | Named logos/testimonials | Nema evidence u repo-u da su stvarni kupci | `site-copy.md:19-21`, `site-copy.md:99-104` |

## Tier-by-tier product decision

### Evaluation tier

Website obećanje: `€0 for 30-60 days`, up to 5 seats, 5,000 queries/month, one workspace, local LLM + audit log, email support only, no custom integrations/migration/dedicated onboarding, expires unless upgraded.

| Claim | Verdict | Šta uraditi |
|---|---|---|
| Up to 5 seats | Must build | Dodati tier config i enforcement u admin user creation. Trenutni `create_user` proverava samo password i duplicate email, bez seat limita. |
| 5,000 queries/month | Must build | Dodati monthly query quota po workspace/tier i blokadu u `/chat` i `/chat/stream` pre graph invocation-a. Trenutno postoji rate limit `30/minute`, ali ne mesečni tier limit. |
| One workspace | Copy correction or build small | Ako app zaista ima samo jedan deployment/workspace, copy može ostati. Ako se u UI pominje workspace switching, treba ukloniti ili implementirati workspace model. |
| Local LLM + audit log | Already mostly OK | Local Ollama i audit log postoje. Treba paziti da audit copy ne obećava više od stvarnih polja. |
| Expires unless upgraded | Must build or remove | Trenutno nema evaluation expiration model. Ili dodati `tier_expires_at` i enforcement, ili izbaciti iz website copy-ja. |
| No custom integrations/migration/onboarding | Service boundary, not app feature | Ovo je prodajni scope, ne mora biti app feature. Zadržati kao jasno ograničenje ponude. |

Minimum za iskren `Evaluation`: seat cap, query quota, expiration, i audit/citation copy usklađen sa realnošću.

### Team tier

Website obećanje: production deployment for a single business unit, up to 50 seats, unlimited queries, SSO SAML/OIDC, 90-day audit retention, Slack/Teams support 24h SLA, hybrid inference + reranker, onboarding & migration support.

| Claim | Verdict | Šta uraditi |
|---|---|---|
| Up to 50 seats | Must build before selling Team | Isti tier enforcement kao Evaluation, samo druga vrednost. |
| Unlimited queries | Must build as explicit policy | Ako je Team unlimited, quota check mora znati da je limit disabled za Team. |
| SSO SAML/OIDC | Must build or remove from Team copy | `ssoOnly` nije SSO. Dok nema OIDC/SAML login flow, IdP config, callback handling i user provisioning policy, ovo ne sme da stoji kao product claim. |
| 90-day audit retention | Build/verify | Postoji retention setting, ali copy "90-day retention" mora biti backed by default config i cleanup ponašanjem. Ne sme se istovremeno tvrditi immutable archive osim za Enterprise. |
| Hybrid inference + reranker | Already mostly OK | Provider mode i reranker postoje. Treba dodati docs/UX da Team setup jasno vodi kroz supported hybrid konfiguraciju. |
| Provider toggle takes effect within 30s | Copy correction or audit build | UI kaže "~30s", ali provider change nije `AuditLog` event. Ako copy kaže "itself audited", dodati `settings_provider_change` audit event. |
| Slack/Teams support, onboarding, migration | Service deliverable | Nije app feature. Može ostati u pricing copy-ju, ali ne prikazivati kao product capability unutar aplikacije. |

Minimum za iskren `Team`: real SSO ili uklonjen SSO claim, tier enforcement, jasan 90d retention, provider-change audit event.

### Enterprise tier

Website obećanje: VPC-peered or air-gapped deployment, unlimited seats and tenants, custom retention + tamper-evident archive, custom policy controls & guard rules, dedicated solutions engineer, custom SLA + on-call rotation.

| Claim | Verdict | Šta uraditi |
|---|---|---|
| VPC-peered / air-gapped | Enterprise roadmap | Ne mora biti u core app-u odmah, ali treba deployment doc/checklist, image mirroring story i offline model/artifact install procedure pre ozbiljne enterprise prodaje. |
| Unlimited seats and tenants | Enterprise roadmap | Trenutni model nema tenant/workspace boundary. Ne prodavati "unlimited tenants" kao već postojeće dok nema tenant modela. |
| Custom retention | Enterprise roadmap | Retention setting postoji, ali enterprise custom retention treba policy + storage behavior + evidence. |
| Tamper-evident archive | Enterprise roadmap, not Evaluation/Team | CSV export je običan CSV. Za Enterprise dodati hash chain/signature i archive manifest. Ne tvrditi ovo za osnovni audit trail dok nije implementirano. |
| Custom policy controls & guard rules | Enterprise roadmap | Postoji hardcoded input/output/content behavior i delimični blocked terms koncept u content filteru, ali nema admin policy builder za custom guard rules. |
| Dedicated solutions engineer / custom SLA | Service deliverable | Može ostati u pricing-u kao usluga, nije app feature. |

Enterprise može ostati na sajtu kao "custom annual contract" samo ako copy jasno implicira da se ove stvari rade kroz enterprise deployment, ne da su sve dostupne u trenutnom self-serve app-u.

## Marketing BS / copy koji treba spustiti

Ove stavke ne treba implementirati sada; treba ih ukloniti, ublažiti ili označiti kao primer/demo dok ne postoji dokaz:

| Copy | Problem | Odluka |
|---|---|---|
| Named logo wall: Nordbank, MERIDIAN, Lumen Health, ATLAS, CIVIC GRID, Halcyon Re | Ako nisu stvarni kupci/piloti, ovo je najopasniji marketing BS. | Remove unless real and approved. |
| Testimonials sa imenima i kompanijama | Bez stvarnih dozvola ovo je lažna socijalna potvrda. | Remove or replace with anonymous "example stakeholder concerns". |
| "0 PII exposures across 14,328 queries" | Precizna metrika bez dataset/evidence. | Remove until measured. |
| "100% blocked terms rejected at the edge" | Nema configurable Settings UI za blocked terms u input guard-u. | Replace with narrower implemented claim or build feature first. |
| "1.4s -> 41ms embed.query p95" | Performance claim bez benchmark evidence. | Remove until benchmarked. |
| "CSV exportable, signed, tamper-evident" | CSV postoji, signed/tamper-evident ne. | Split: "CSV exportable" now; tamper-evident only Enterprise roadmap. |
| "Output guard rejects responses without at least one citation" | OutputFilter to ne radi. | Build or remove. |
| "All systems operational / all documents indexed" | Status pill ne postoji i "all indexed" mora biti live state. | Build real status indicator or remove. |

## Plan za nadogradnju

### Phase 1: Make Evaluation honest

Goal: Možeš prodavati/free-trial Evaluation bez preterivanja.

1. Dodati tier config model:
   - `tier`: `evaluation | team | enterprise`
   - `max_seats`
   - `monthly_query_limit`
   - `expires_at`
2. Enforce seat limit u admin user creation.
3. Enforce monthly query limit u `/chat` i `/chat/stream`.
4. Dodati admin-visible usage state: current seats, current monthly queries, expiry date.
5. Uskladiti website copy:
   - Evaluation: 5,000 queries/month, not 10k. `site-copy.md` trenutno ima konflikt: pricing kaže 5,000, FAQ kaže 10k.
   - Ne pominjati immutable archive u Evaluation.
6. Testovi:
   - user creation blokira 6. aktivnog korisnika na Evaluation.
   - chat blokira 5,001. query u mesečnom periodu.
   - Team tier ne blokira query zbog monthly limit-a.
   - expired Evaluation vraća jasan error.

### Phase 2: Make audit and citation claims defensible

Goal: Compliance copy ne sme da obećava više od pipeline-a.

1. Odlučiti product policy:
   - Opcija A: hard-require citations za svaki non-fallback odgovor.
   - Opcija B: spustiti copy na "answers include citations when grounded in retrieved sources".
2. Ako biramo A:
   - Output guard mora da proveri citation presence kroz state/citations, ne samo regex u tekstu.
   - Long answer policy mora biti stvaran block ili copy mora reći "warns on unusually long answers".
3. Dodati audit metadata za guard decisions ako se zadržava claim "guard decision logged".
4. Testovi:
   - generated answer bez citations se blokira ili se vraća fallback.
   - long answer ponašanje odgovara copy-ju.
   - audit row sadrži guard metadata koji copy obećava.

### Phase 3: Make Team sellable

Goal: Team tier ne sme da sadrži placeholder SSO.

1. Ili implementirati OIDC first, SAML later, ili ukloniti `SSO (SAML, OIDC)` iz Team tier-a.
2. Ako implementiramo OIDC:
   - IdP issuer/client id/client secret config.
   - callback route.
   - email/domain matching.
   - first-admin bootstrap policy.
   - `ssoOnly` tek tada postaje enforcement toggle.
3. Dodati `settings_provider_change` audit event:
   - old/new provider mode.
   - old/new embedding source.
   - admin user id.
   - timestamp and trace/correlation id if available.
4. Testovi:
   - provider mode change creates `AuditLog`.
   - OIDC login creates/links user according to policy.
   - `ssoOnly=true` blocks password login only after SSO config is valid.

### Phase 4: Enterprise roadmap, not immediate build

Goal: Ne blokirati prve prodaje enterprise feature-ima, ali ne lagati CISO buyer-u.

1. Tamper-evident audit export:
   - CSV hash chain or manifest hash.
   - HMAC or signing key.
   - export metadata with verification instructions.
2. Immutable archive:
   - S3 Object Lock or customer-provided WORM destination.
   - archive-before-delete in cleanup.
   - archive manifest stored separately.
3. Air-gap deployment pack:
   - image list.
   - model artifact list.
   - no-outbound runtime verification.
   - offline install runbook.
4. Controls mapping doc:
   - map audit fields, guards, spans to SOC 2 / ISO 27001 / NIST 800-53 families.
5. Multi-tenant:
   - only plan after first Team deployments validate demand.

## Copy changes recommended now

These changes can happen before app implementation, because they reduce risk without weakening the offer:

- Replace fake customer logos/testimonials with "Built for regulated teams handling sensitive data" until real references exist.
- Change "archived to immutable storage" to "retention configurable; immutable archive available on Enterprise deployments" until archive exists.
- Change "CSV exportable, signed, tamper-evident" to "CSV exportable" for Evaluation/Team; keep signed/tamper-evident only under Enterprise roadmap.
- Change "SSO (SAML, OIDC)" to "SSO available on Team deployments" only after implementation, or "SSO planned" if selling today.
- Remove exact metrics unless backed by real benchmark/audit data.
- Fix pricing conflict: Evaluation is either 5,000 queries/month or 10,000 queries/month, not both.

## What not to build now

Do not build these before Evaluation/Team basics:

- Multi-tenant architecture.
- Full SAML if OIDC can close Team pilots first.
- SOC 2 / ISO / NIST mapping automation.
- Full marketing landing page inside app.
- Custom policy rule builder before there is buyer demand.
- Tempo/Honeycomb UI selection; env-configured OTLP is enough for now.

## Implementation acceptance criteria

The next implementation batch is done only when:

- Evaluation tier enforces seats, monthly queries and expiry.
- Team tier either has real OIDC/SSO or website copy no longer promises SAML/OIDC.
- Audit copy no longer claims immutable/tamper-evident behavior outside Enterprise.
- Citation copy matches actual output guard behavior.
- Provider mode changes are persisted to `AuditLog` if website says the toggle is audited.
- All fake customer proof is removed or backed by real permission.

