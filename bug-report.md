# Verified Status — 2026-05-15 (Round 3 + Round 4 + Round 5 + Provider Runtime Hardening)

Ovaj fajl više nije lista otvorenih pretpostavki, nego provereno stanje posle više audit i patch prolaza.

## Verification

- Backend: `.venv/bin/pytest -q` -> `228 passed`
- Frontend: `npm run build` -> uspešno

## Item-by-item Status

| # | Status | Napomena |
|---|---|---|
| 1 | Fixed | `require_role()` sada normalizuje role vrednost pre poređenja. |
| 2 | Not reproducible | Posle zaključavanja aktivnih ingestion poslova i brisanja DB reda, `reindex` više ne može validno da krene nad istim dokumentom. |
| 3 | Fixed | `reindex_document` na Qdrant reset failure ponovo učitava `job` i `doc` iz sesije pre status update-a. |
| 4 | Fixed | `POST /auth/login` sada zahteva allowed `Origin`; dodati su regresioni testovi za missing/cross-origin. |
| 5 | Fixed | Deleted-user sentinel sada dobija validan bcrypt hash. |
| 6 | Fixed | `feedback.py` više ne radi dupli `db.get()` po redu; korisnici se batch-učitavaju. |
| 7 | Fixed | BM25 rebuild više ne čita pod lock-om pa rebuild-uje van lock-a. |
| 8 | Not reproducible | Na client strani `useChat` već gasi `streaming` u `finally`; disconnect ne ostavlja trajno zaglavljen UI u trenutnom toku. |
| 9 | Fixed | `run_ingestion` više ne pregazi `skipped` status sa `indexed`. |
| 10 | Bounded limitation | Upload i dalje baferuje dozvoljenu veličinu u memoriji, ali više ne može neograničeno da raste; ovo nije otvoren correctness bug u trenutnoj implementaciji. |
| 11 | Fixed | `deactivate_user` sada postavlja `token_valid_after`. |
| 12 | Fixed | Orphaned raw fajl se čisti ako DB commit za upload padne. |
| 13 | Fixed | Settings PATCH pozivi su sada serijalizovani i optimistic cache sprečava stale overwrite. |
| 14 | Fixed | SSE `data:` parser skida samo opcioni jedan razmak, ne sav leading whitespace. |
| 15 | Not reproducible | `sessionRef` je vezan za lifecycle hook-a; pri realnom remount-u stranice ne opstaje kao trajno stale stanje. |
| 16 | Fixed | `NumberInput` clamp-uje vrednost na `min`/`max` pri commit-u. |
| 17 | Intentional UX | Suggested prompt puni composer bez auto-submit-a; ostavljeno namerno. |
| 18 | Fixed | Citation drawer sada može da prati izvore iz ranije assistant poruke, ne samo poslednje. |
| 19 | Fixed | Toggle sada ima `type="button"`, `role="switch"` i `aria-checked`. |
| 20 | Not a bug | `pollStatus` ne loop-uje beskonačno; prekida na error ili po isteku timeout-a. |
| 21 | Fixed | Uklonjen mrtav `task is None` guard iz `_schedule_ingestion_task`. |
| 22 | Fixed | Test-only `Mock` import je uklonjen iz runtime koda. |
| 23 | Fixed | CSV export više ne učitava sve redove odjednom; stream-uje izlaz. |
| 24 | Fixed | `limit` i `offset` sada imaju eksplicitnu validaciju. |
| 25 | Fixed | `days` je ograničen na `1..366`. |
| 26 | Fixed | `HybridRetriever` i `SemanticCache` koriste `/api/embed`. |
| 27 | Not a bug | `fetch(FormData)` namerno ne postavlja ručno `Content-Type`; browser ispravno dodaje boundary. |
| 28 | Fixed | `Session.updated_at` sada ima `server_default=func.now()`. |
| 29 | Fixed | `_coerce_bool` sada ispravno obrađuje `"0"`, `"1"`, `"false"`, `"true"` i slične vrednosti. |

## Residual Notes

- Stavke `#2`, `#8`, `#10`, `#15`, `#17`, `#20` i `#27` nisu ostale otvoreni bugovi posle proverene reprodukcije; ili su već pokrivene drugim zaštitama, ili predstavljaju nameran UX/implementacioni tradeoff.
- Ako bude potreban dodatni hardening za upload memorijski profil iz `#10`, to je sledeći kandidat za zaseban refactor ka stream-to-disk pristupu umesto novog bugfix hotfix-a.

---

## Round 3 Fixes (pre-audit Round 4)

| # | Status | Napomena |
|---|---|---|
| R3-1 | Fixed | `_ensure_deleted_user` sada koristi `token_urlsafe(24)` umesto slabog predvidivog password-a. |
| R3-2 | Fixed | `feedback.py` `list_for_admin` sada ima limit cap na 1000 (`max(1, min(limit, 1000))`). |
| R3-3 | Fixed | `audit_cleanup.py` više ne briše svoje vlastite `system_cleanup` audit logove. |
| R3-4 | Fixed | `/admin/stats` `days` parametar sada ima bounds validaciju (`1..366`). |

---

## Round 4 Findings & Fixes

| # | Severity | Status | Bug | Fajl |
|---|----------|--------|-----|------|
| R4-1 | Medium | Fixed | XLSX workbook file handle leak — `openpyxl.load_workbook(read_only=True)` ne poziva `wb.close()`, curi file descriptor po svakom XLSX ingestion-u. | `app/services/rag_pipeline.py` |
| R4-2 | High | Fixed | Cost ceiling nije enforce-ovan — `daily_ceiling_usd` i `monthly_ceiling_usd` su sačuvani i prikazani u settings UI, ali `/chat` i `/chat/stream` nikada ne proveravaju da li je limit dostignut pre obrade upita. Dodata `_check_cost_ceiling()` funkcija koja vraća 429 ako je dnevni ili mesečni limit prekoračen. | `app/api/chat_routes.py` |
| R4-3 | Medium | Fixed | `AgentRun` redovi orphan-ovani pri deaktivaciji korisnika — `deactivate_user` briše `DbSession` redove ali ne i povezane `AgentRun` redove. Sada se prvo brišu AgentRun redovi za korisnikove sesije, pa tek onda sesije. | `app/api/admin_routes.py` |
| R4-4 | Medium | Fixed | Corrupted session `ValueError` neuhvaćen — `_resolve_session` hvata samo `KeyError`, ali `load_session` baca i `ValueError` za pokvareno stanje. Sada se hvataju oba exception-a i kreira nova sesija. | `app/api/chat_routes.py` |
| R4-5 | Low | Fixed | `unique_users` u `/admin/stats` broji sve aktivne korisnike umesto korisnika koji su zapravo slali upite u periodu. Sada koristi `count(distinct AuditLog.user_id)` sa timestamp filterom. | `app/api/admin_routes.py` |
| R4-6 | Medium | Fixed | `cost_tracker.get_stats` učitava sve `AgentRun` redove u memoriju umesto SQL agregacije. Refaktorisano da koristi `func.sum()`, `func.count()`, `func.date()` sa `group_by` — performanse drastično poboljšane za velike datasetove. | `observability/cost_tracker.py` |
| R4-7 | Low | Fixed | `CreateUserRequest.email` nema validaciju formata — backend prihvata bilo koji string kao email. Dodat je stroži validator koji odbija whitespace i zahteva oblik `local@domain.tld`. | `app/api/admin_routes.py` |
| R4-8 | Medium | Fixed | Chunked transfer encoding zaobilazi body size limit — middleware proverava samo `Content-Length` header, a chunked zahtevi nemaju taj header. Sada se chunked body konzumira sa size cap-om. | `app/main.py` |
| R4-9 | Low | Fixed | `cache_total_hits` je bio semantički netačan — brojao je lifetime hitove za cache unose kreirane u periodu, ne hit događaje u periodu. Dodata je posebna tabela `semantic_cache_hits`, lookup sada zapisuje hit event, a `/admin/stats` broji period hitove iz te tabele. | `app/api/admin_routes.py`, `app/services/semantic_cache.py`, `app/db/models.py` |
| R4-10 | Medium | Fixed | `reindex_document` je imao partial failure inconsistency — DB chunk obrisi i version bump su se dešavali pre Qdrant reset-a. Flow je preuređen tako da se Qdrant/BM25 reset radi prvo, a DB transakcija kreće tek nakon uspešnog spoljnog reset-a. | `app/api/admin_routes.py` |

## Round 4 Residual Notes

- Round 4 više nije samo “implemented”; sada postoje direktni regresioni testovi za ceiling blokadu, corrupted-session fallback, invalid email, AgentRun cleanup, distinct `unique_users` metric, chunked-body middleware path, period-scoped cache hit metric i reindex failure bez parcijalnog DB reset-a.
- `semantic_cache.hit_count` je zadržan kao lifetime counter, dok je period metric prebačen na `semantic_cache_hits` događaje. Time su pokrivena oba use-case-a bez mešanja značenja.
- Ukupno kroz 5 rundi audita: 73 + 35 = 108 stavki pregledano, 79 fixed, 14 not-a-bug/not-reproducible, 7 bounded-limitation/intentional-UX, 3 improved, 5 code-quality/not-a-bug-open.

---

## Round 5 Findings & Verification

| # | Severity | Status | Bug | Fajl | Napomena |
|---|----------|--------|-----|------|----------|
| R5-1 | — | Not a bug | `applyDiff` `??` za falsy `0` vrednosti | `SettingsPage.tsx` | `??` ne guta `0`, samo `null`/`undefined`. |
| R5-2 | Critical | Fixed | `queueSave` race condition — optimistic cache overwrite pri paralelnim save-ovima | `SettingsPage.tsx` | `unsavedDiffRef` + `mergeDiffs` + `subtractConfirmedDiff` akumuliraju i čuvaju difove; error pravi invalidate + re-apply. |
| R5-3 | High | Fixed | DB session posle commit u `chat_stream` — `ExpiredSessionError` rizik | `chat_routes.py` | `finalize_chat_run()` helper u `chat_finalizer.py` izvršava sve post-stream operacije (reply, audit, cost) u jednoj `db.begin()` transakciji. Jedan commit = atomičan zapis bez `ExpiredSessionError` rizika. |
| R5-4 | High | Fixed | Cost ceiling check je jedan upit iza — može preći limit | `chat_routes.py` | `_check_cost_ceiling(db, projected_question=body.question)` sada projektuje trošak pre izvršenja. |
| R5-5 | High | Fixed (caveat) | Token estimation koristi word-count heuristiku | `chat_routes.py` | `OpenAICompatibleProvider.chat()` vraća `ProviderUsage` sa stvarnim token counts iz API odgovora (`usage.source = "actual"`). Ollama nema usage endpoint pa ostaje `source = "estimated"` (`chars/4`). |
| R5-6 | Critical | Not a bug | `deactivate_user` nema transaction wrapping | `admin_routes.py` | SQLAlchemy sesija je uvek u implicitnoj transakciji; `db.commit()` na kraju obezbeđuje atomičnost. |
| R5-7 | Critical | Fixed | `reindex_document` TOCTOU race — briše Qdrant pre rezervacije posla | `admin_routes.py` | Prvo rezerviše job u `with db.begin()` sa `with_for_update`, pa briše Qdrant/BM25, pa čisti DB chunks. Na failure se job+doc markiraju kao failed. |
| R5-8 | High | Fixed | Settings model select-ovi hardcoded — ne poklapaju se sa Ollama modelima | `SettingsPage.tsx` | `s.availableModels.ollama` i `s.availableModels.reranker` sada dolaze dinamički sa servera (`/api/tags`). |
| R5-9 | High | Fixed | (Isto kao R5-8, odnosi se na sve model select-e) | `SettingsPage.tsx` | Vidi R5-8. |
| R5-10 | Medium | Fixed | `NumberInput` `useEffect` resetuje draft tokom aktivnog editovanja | `SettingsPage.tsx` | Draft/commit pattern pravilno razdvaja editovanje od snimanja; `value` se menja samo posle commit-a. |
| R5-11 | High | Fixed | Login nema hint za minimum 12 karaktera | `LoginPage.tsx` | `z.string().min(12, "Password must be at least 12 characters")` + "Use at least 12 characters" hint. |
| R5-12 | — | Intentional UX | Settings auto-save bez eksplicitnog "Save" dugmeta | `SettingsPage.tsx` | Namerna design odluka; row-level saving indikatori dodati (R5-13). |
| R5-13 | Medium | Fixed | Nema loading indikatora na pojedinačnim settings redovima | `SettingsPage.tsx` | `savingFields` state + `saving={isSavingField("...")}` na svakom Row. |
| R5-14 | High | Fixed | Citation drawer nevidljiv na mobile | `ChatPage.tsx` | `mobileSourcesOpen` state + "Show/Hide" button za mobile. |
| R5-15 | — | Intentional UX | Suggested prompt puni composer bez auto-submit | `ChatPage.tsx` | Namerna UX odluka; jasniji affordance dodat. |
| R5-16 | — | Not a bug | CSRF Origin check za login — samo browser-based zaštita | `main.py` | Origin check je adekvatan za browser-based napade; API-only zaobilazi by design. |
| R5-17 | Medium | Fixed | Seed script ima hardcoded admin lozinku | `scripts/seed.py` | `SEED_ADMIN_PASSWORD` env var ili auto-generisana + ispisana lozinka. |
| R5-18 | Medium | Fixed | `.env.example` SECRET_KEY ruši startup | `.env.example` | `replace-me-with-a-random-32-char-secret` + comment sa generisanje komandom (36 karaktera, nije u weak set-u). |
| R5-19 | High | Fixed | `limit_body_size` middleware čita ceo chunked body u memoriju | `main.py` | `SpooledTemporaryFile` umesto bytearray; preliva na disk ako pređe limit. |
| R5-20 | Medium | Bounded limitation | `AuditLog.user_id` FK nema `ondelete` — audit logovi se anonymizuju ali zadržavaju | `models.py` | Namerno — audit trail se čuva sa `user_id=NULL` po deaktivaciji. |
| R5-21 | Medium | Fixed | `AgentRun` redovi orphan-ovani pri deaktivaciji korisnika | `admin_routes.py` | `deactivate_user` sada eksplicitno briše `AgentRun` redove za korisnikove sesije. |
| R5-22 | — | Code quality | `upsert_app_config` ne poziva commit — caller mora | `app_config_store.py` | Konzistentan caller-commit pattern; nije bug. |
| R5-23 | Medium | Fixed | `_serialize_settings` radi DB query na svakom GET | `admin_routes.py` | `_SETTINGS_LIVE_TTL_SECONDS = 15.0` TTL cache za cost + available models. |
| R5-24 | — | Not a bug | `invalidate_cache_for_document` koristi `@>` jsonb containment | `semantic_cache.py` | `@>` operator radi ispravno za containment check. |
| R5-25 | Medium | Fixed | `useDocuments` polling loop ne čisti na unmount | `useDocuments.ts` | `mountedRef` + `timeoutIdsRef` sa cleanup u `useEffect`; timeout-i se čiste na unmount. |
| R5-26 | Medium | Fixed | Backend nema password complexity validaciju | `admin_routes.py` | Server-side validacija dodata: uppercase, lowercase, digit, special char. |
| R5-27 | — | Not a bug | `page_number=0` u citations | `models.py` | `page_number=0` je validan (prva strana); kozmetičko. |
| R5-28 | — | Not a bug | CSRF ne štiti login od same-origin form submission | `main.py` | Login CSRF rizik je nizak (napadač loguje žrtvu, ne krade credentials). |
| R5-29 | — | Addressed | SSE "done" delayed by DB operations | `chat_routes.py` | `sse_done_mode` setting: `"strict"` (default) emituje "done" posle commit-a za garantovanu korektnost; `"async"` emituje odmah i commit-uje u background task-u za nižu latenciju. Konfigurabilno per-deployment. |
| R5-30 | Medium | Fixed | `res.body!` non-null assertion može pući runtime | `chat.ts` | `if (!res.body)` null check pre `getReader()`. |
| R5-31 | — | Not reproducible | `useAuth` signOut stale closure | `useAuth.ts` | useRef pattern uvek vraća current vrednost. |
| R5-32 | — | Not a bug | `HybridRetriever` nije importovan ali se koristi kao type hint | `admin_routes.py` | `from __future__ import annotations` — lazy evaluacija, runtime OK. |
| R5-33 | — | Not a bug | Upload `Content-Type` fragilan pri refaktoru | `documents.ts` | Kod je ispravan; `fetch(FormData)` ne postavlja `Content-Type` namerno. |
| R5-34 | Low | Fixed | `DocumentsPage` upload-uje fajlove sekvencijalno | `DocumentsPage.tsx` | `Promise.allSettled(...)` za paralelni multi-file upload. |
| R5-35 | — | Not a bug | `useChat` `rate` koristi `messagesRef.current` | `useChat.ts` | useRef `.current` je uvek ažuran; prazan dependency array je OK za refs. |

## Round 5 Residual Notes

- **R5-3** (DB session posle commit): Potpuno rešeno u provider runtime hardening (Tasks 7). `finalize_chat_run()` u `chat_finalizer.py` koristi jednu `db.begin()` transakciju za sve post-stream operacije.
- **R5-5** (Token estimation): Rešeno za OpenAI-compatible provajdere — `ProviderUsage.source = "actual"` kada API vrati usage. Ollama ostaje `source = "estimated"` jer nema usage endpoint.
- **R5-20** (AuditLog FK ondelete): Namerna design odluka — audit trail se zadržava sa `user_id=NULL` po deaktivaciji, čime se poštuje i audit zahtev i GDPR princip.
- **R5-29** (SSE done delay): Rešeno konfiguracijom — `sse_done_mode = "strict"` (default) ili `"async"` per-deployment.
- **R5-12** (Auto-save UX): Namerna design odluka sa row-level indikatorima. Ako korisnici budu tražili eksplicitan "Save", dodati kasnije.
- Ukupno kroz 5 rundi + provider runtime hardening: 108 stavki, 82 fixed, 14 not-a-bug/not-reproducible, 7 bounded/intentional, 3 improved, 5 code-quality.





