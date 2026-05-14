# Verified Status — 2026-05-14

Ovaj fajl više nije lista otvorenih pretpostavki, nego provereno stanje posle novog audita i patch prolaza.

## Verification

- Backend: `.venv/bin/pytest -q` -> `202 passed, 6 skipped`
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
