# Verified Status — 2026-05-14 (Round 3 + Round 4)

Ovaj fajl više nije lista otvorenih pretpostavki, nego provereno stanje posle više audit i patch prolaza.

## Verification

- Backend: `.venv/bin/pytest -q` -> `213 passed, 6 skipped`
- Frontend: `npm run build` -> prolazi

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
- Ukupno kroz 4 runde audita: 32 + 29 + 4 + 8 = 73 bugova pronađeno, 67 fixed, 5 not-reproducible/intentional, 1 design tradeoff/acceptable.
