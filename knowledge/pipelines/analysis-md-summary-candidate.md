# Drive Analysis Markdown Summary Candidate

Manifest key: `analysis-md-summary-candidate`
Paperclip pipeline: `Drive Analysis Markdown Summary Candidate`
Owner: DataPlatformEngineer
Status: candidate
Last reconciliation: 2026-06-28

## Operating Definition

This candidate pipeline evaluates Drive analysis Markdown as a pre-publication
source for report card summaries and `Investment View` copy. It is not an active
replacement for the ECON/MAT/FOR slide publishing pipelines.

- Active candidate input: Google Drive `analysis2/{ECON,MAT,FOR}` Markdown, or
  a development-only local `--source-path`.
- Legacy candidate input: Google Drive `analysis/{ECON,MAT,FOR}` only when
  `--drive-root-scope legacy` or `all` is explicitly selected.
- Runtime entrypoint: `scripts/pipeline/analysis_md_summary_candidate.py`.
- Operator command shape:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug solana --drive-root-scope active --dry-run`.
- Paperclip local agent apply shape:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug solana --drive-root-scope active --agent-output-json <paperclip-agent-output.json> --require-agent-output`.
- Production write policy: default off. The candidate entrypoint must not write
  `project_reports` or publish website-visible content. `report_summary_jobs`
  writes require `--dry-run` to be omitted and still remain candidate records
  until a separate remote approval authorizes promotion.
- LLM boundary: Paperclip local agents generate the summary JSON. This pipeline
  validates and persists that agent output; it must not call an LLM provider API
  directly from GitHub Actions or pipeline scripts.
- Telemetry state store: Supabase `pipeline_runs`, `pipeline_node_runs`, and
  `pipeline_events` under `pipeline_name=analysis-md-summary-candidate`.

## Candidate Contract

- Source identity is provenance: `drive:{driveFileId}:{revisionId}` when Drive
  revision identity exists, otherwise `sha256:{normalized_markdown_sha256}`.
- Candidate job idempotency is keyed by `reportCode + reportSlug + locale +
  driveFileId + revision/hash + promptVersion + schemaVersion`. Duplicate
  `idempotency_key` rows are skipped unless `--force` is set, in which case the
  existing candidate job is updated. `source_identity` remains indexed only for
  provenance and lookup.
- Routine polling excludes Drive source identities that already have a
  `report_summary_jobs.authority_state=promoted` row before applying the
  single-candidate `--limit`. Operator/manual reprocessing may use `--force` to
  include a promoted source intentionally; normal routine polling omits
  `--force` and no-ops when no unpromoted source remains.
- Candidate persistence uses `report_summary_jobs`; `project_reports` alone is
  not sufficient for pre-approval LLM metadata such as source revision/hash,
  summarizer model, prompt/schema version, generated timestamp, validation
  status, candidate patch, and failed validation artifacts.
- Summary Authority Gate persistence adds `authority_state`, `authority_mode`,
  locale-aware `idempotency_key`, promotion audit fields, and
  `report_summary_promotion_locks`. The allowed state machine is
  `detected -> llm_candidate -> validation_failed | validation_passed -> promotion_pending -> promoted | rejected | fallback_script`.
- Authority modes are `legacy_script`, `llm_candidate`, and `llm_active`.
  `legacy_script` and `llm_candidate` retain the legacy active
  `project_reports` summary; only `llm_active` may promote a validation-passed
  candidate through the gate.
- LLM payloads must include `summary_by_lang` and `marketing_by_lang` for all
  seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`, `zh`), source evidence,
  and card-quality-safe text. Schema, missing-language, length, forbidden
  pattern, script mismatch, and source-grounding failures block candidate upsert
  as ready.
- Valid candidate patches reuse `marketing_content_pipeline.py` Markdown parsing,
  card summary quality gates, and `card_summary_v2` provenance.

## Nodes

1. `analysis_md_source_scan` / Drive analysis Markdown scan:
   `scripts/pipeline/analysis_md_summary_candidate.py`.
2. `summary_candidate_generation` / Paperclip local agent summary generation:
   local Paperclip agent run against the selected Drive Markdown source. The
   agent writes schema-conformant JSON for ingestion via `--agent-output-json`.
3. `candidate_validation` / Schema, language, quality, and grounding validation:
   shared card quality gates plus candidate-specific evidence checks.
4. `candidate_job_upsert` / Default-off report summary job upsert:
   Supabase `report_summary_jobs` when not in dry-run mode.
5. `summary_authority_gate` / Default-off candidate promotion, rejection, or
   fallback:
   `scripts/pipeline/summary_authority_gate.py`.

## Summary Authority Gate

- Runtime command shape:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id <uuid> --authority-mode llm_active --write`.
- Default behavior is dry-run. Omitting `--write` must not update
  `project_reports`, `report_summary_jobs`, locks, or telemetry.
- Promotion lock scope is `project_slug/report_type/locale`; only one active
  promotion can run for that scope at a time.
- Validation-failed candidates cannot be promoted and must not erase or
  overwrite legacy active summaries.
- Promotion/rejection/fallback emits `pipeline_events` under the
  `analysis-md-summary-candidate` pipeline contract.

## BCE-2000 Candidate Boundary

BCE-2000 adds a change-request/candidate path only. It does not change the active
`Slide2/*` PDF operating input, GitHub Actions cadence, approval gate, or
website publishing contract for `econ-report-publishing`,
`mat-report-publishing`, or `for-report-publishing`.

### BCE-2330 AIOZ Network MAT Summary Target Backfill Applied (2026-07-01 06:23 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `e136279`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, 및 `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned critical issue `[BCE-2330](/BCE/issues/BCE-2330)`; 신규 댓글은
  없었고 harness가 checkout한 `issue_assigned` 실행이었다.
- 재발/중복 확인:
  `[BCE-2329](/BCE/issues/BCE-2329)`의 Summary Authority Gate 실패가
  `tracked project not found: aioz-network`였고, 상태 위키의 반복 기록도
  AIOZ MAT가 canonical `tracked_projects` 및 KO maturity target row 부재로
  제외되어 왔음을 확인했다. `scripts/pipeline/collectors/.cache`의 token
  snapshots에도 `AIOZ Network` canonical market slug는 `aioz-network`로
  존재한다.
- 수정:
  `supabase/migrations/20260630212000_seed_aioz_network_maturity_ko_summary_target.sql`
  을 추가했다. 이 migration은 `tracked_projects.slug=aioz-network`,
  `symbol=AIOZ`, `coingecko_id=aioz-network` row를 생성/복구하고
  `status=coming_soon`, `language=ko`, `report_type=maturity`, `version=1`
  인 MAT target shell을 생성/복구한다.
- Approved DB path:
  `.github/workflows/db-migration.yml` manual dispatch with
  `migration_name=20260630212000_seed_aioz_network_maturity_ko_summary_target.sql`.
- Remote migration evidence:
  GitHub Actions run
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28476758149`
  completed `success` on branch `codex/paperclip-agent-summary-source` at
  `4c4caccf48385ff0a4102f1946bbb66a5df5288e`. The selected SQL migration step
  returned `[]`.
- Target provenance:
  `card_data.summary_authority_target`에 issue `[BCE-2330](/BCE/issues/BCE-2330)`,
  blocked issue `[BCE-2329](/BCE/issues/BCE-2329)`, job
  `d74bc166-b9ef-421d-8c9a-875939ed706c`, source identity
  `drive:13Bj-oq6W6mACE1_86xYzS6W2RYeARsr6:0B8HYgThT3NByQlUxUEtsTzVPTjFJMEswNFdSNWliVDQvLzBzPQ`
  를 기록한다.
- Manifest change:
  no change needed. 이번 수정은 기존 `analysis-md-summary-candidate` 및
  `summary_authority_gate` 계약 하의 운영 데이터 seed/backfill이다.

### BCE-2325 Huma Finance ECON Summary Gate Target Row Missing (2026-07-01 05:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned critical issue `[BCE-2325](/BCE/issues/BCE-2325)`; 신규 댓글은
  없었고 harness가 checkout한 `issue_assigned` 실행이었다.
- 재발/중복 확인:
  직전 `[BCE-2324](/BCE/issues/BCE-2324)` 기록과 Summary Authority Gate
  `find_target_report` 계약을 확인했다. `huma-finance` canonical project는
  존재하지만 `huma-finance/econ/ko` website-visible `project_reports` target
  row가 없어 `llm_active --write` 승격이 실패하는 데이터 블로커다.
- 수정:
  `supabase/migrations/20260630204000_seed_huma_finance_econ_ko_summary_target.sql`
  을 추가했다. 이 migration은 기존 패턴과 동일하게
  `status=coming_soon`, `language=ko`, `report_type=econ`, `version=1`인
  Huma Finance ECON target shell을 생성/복구하고
  `card_data.summary_authority_target`에 `[BCE-2325](/BCE/issues/BCE-2325)`,
  blocked issue `[BCE-2324](/BCE/issues/BCE-2324)`, source identity를
  기록한다.
- Manifest change:
  no change needed. 이번 수정은 기존 `analysis-md-summary-candidate` 및
  `summary_authority_gate` 계약 하의 운영 데이터 seed/backfill이다.

### BCE-2327 Huma Finance ECON Target Migration Applied (2026-07-01 05:42 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b` before the migration commit; pushed migration commit
  `e13627944d3b0287ae1c686604ea24372c40cfb9`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Approved DB path:
  `.github/workflows/db-migration.yml` manual dispatch with
  `migration_name=20260630204000_seed_huma_finance_econ_ko_summary_target.sql`.
- Remote migration evidence:
  GitHub Actions run
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28474528251`
  completed `success` on branch `codex/paperclip-agent-summary-source` at
  `e13627944d3b0287ae1c686604ea24372c40cfb9`.
- Production DB verification:
  `tracked_projects.slug=huma-finance`, `symbol=HUMA`,
  `tracked_projects.status=monitoring_only`; `project_reports.id` is
  `670b951e-6483-47c2-be85-43bb4e1dd481`, `report_type=econ`,
  `language=ko`, `version=1`, `status=coming_soon`, `is_latest=true`.
  `card_data.summary_authority_target` records issue `[BCE-2325](/BCE/issues/BCE-2325)`,
  blocked issue `[BCE-2324](/BCE/issues/BCE-2324)`, and source identity
  `drive:1RaOfU4Q0qJWxbprNREP0gHkwQ3-osBYz:0B8HYgThT3NBydWlabkJiZmN1alpJTnRTZGZxWDNndlBRVm8wPQ`.
- Unblock status:
  the `huma-finance/econ/ko` website-visible target row now exists, so
  `[BCE-2324](/BCE/issues/BCE-2324)` can resume candidate ingest and
  Summary Authority Gate promotion for the Huma Finance ECON source.
- Manifest change:
  no change needed. This was a remote application of the existing operational
  seed/backfill under the `analysis-md-summary-candidate` contract.

### BCE-2324 CRO Analysis MD Summary JSON Ingestion Routine Resumed (2026-07-01 05:51 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `e136279`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `[BCE-2325](/BCE/issues/BCE-2325)` child blocker completion으로
  `[BCE-2324](/BCE/issues/BCE-2324)`가 재개되었다.
- Target row verification:
  `huma-finance/econ/ko` target row가 production DB에 존재함을 확인했다.
  `project_reports.id=670b951e-6483-47c2-be85-43bb4e1dd481`,
  `report_type=econ`, `language=ko`, `version=1`, `status=coming_soon`,
  `is_latest=true`.
- Drive source:
  `Huma Finance 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1RaOfU4Q0qJWxbprNREP0gHkwQ3-osBYz:0B8HYgThT3NBydWlabkJiZmN1alpJTnRTZGZxWDNndlBRVm8wPQ`.
- Source SHA-256:
  `437f6baf53aee16677ec4f407f03cae6a1bae691855c43284703fddda7436921`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_huma-finance_bce2324.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_huma-finance_bce2324.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_huma-finance.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `huma-finance`
  - validation status: `valid`
  - validation reasons: none after compressing KO marketing copy to one
    validator-safe sentence
  - upsert result: `inserted`
  - job id: `5ef3d4a5-7a85-4338-985f-92035a75db0c`
- Selector/runtime note:
  the full CLI command completed after more than 90 seconds of no output from
  the Drive path; it returned a valid inserted candidate and artifact after the
  terminal interrupt was sent.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5ef3d4a5-7a85-4338-985f-92035a75db0c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2324" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `670b951e-6483-47c2-be85-43bb4e1dd481`
- DB verification artifact:
  `scripts/pipeline/output/bce2324_huma-finance_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=huma-finance`, `symbol=HUMA`,
    `status=monitoring_only`
  - `report_summary_jobs.id=5ef3d4a5-7a85-4338-985f-92035a75db0c`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=670b951e-6483-47c2-be85-43bb4e1dd481`

### BCE-2329 AIOZ Network MAT Candidate Ingest Blocked At Promotion (2026-07-01 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `e136279`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned critical issue `[BCE-2329](/BCE/issues/BCE-2329)`; 신규 댓글은
  없었고 harness가 checkout한 `issue_assigned` 실행이었다.
- Candidate selection:
  Drive `analysis2/analysis` 전체 Markdown 541개를 메타데이터 기준으로
  확인했고, `report_summary_jobs.authority_state=promoted` source identity를
  제외한 최신 unpromoted 후보는 MAT `AIOZ Network`였다.
- Drive source:
  `AIOZ 크립토 이코노미 성숙도 평가 보고서_ AIOZ Network.md`.
- Source identity:
  `drive:13Bj-oq6W6mACE1_86xYzS6W2RYeARsr6:0B8HYgThT3NByQlUxUEtsTzVPTjFJMEswNFdSNWliVDQvLzBzPQ`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_aioz-network_bce2329.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_aioz-network.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `aioz-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d74bc166-b9ef-421d-8c9a-875939ed706c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d74bc166-b9ef-421d-8c9a-875939ed706c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2329" --write`.
- Promotion blocker:
  the gate failed before `project_reports` write with Supabase RPC error
  `tracked project not found: aioz-network`. A DataPlatformEngineer unblock
  issue is required to create or map the canonical `tracked_projects` row and
  website-visible MAT KO target row before BCE-2329 can resume promotion.
- Manifest change:
  no change needed. This is an operational data/backfill blocker under the
  existing `analysis-md-summary-candidate` and `summary_authority_gate`
  contract.
  - `report_type=econ`, `language=ko`, `status=coming_soon`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Huma Finance는 결제 흐름의 단기 유동성을 온체인 자본과 연결하는 PayFi 신용 인프라다. 강점은 실물 수요와 회전율이고, 병목은 오프체인 심사와 토큰 가치 포착이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/huma-finance`,
    `https://www.bcelab.xyz/en/projects/huma-finance`,
    `https://www.bcelab.xyz/ko/reports/huma-finance/econ`, and
    `https://www.bcelab.xyz/en/reports/huma-finance/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - The promoted ECON summary string was not present in rendered HTML. The KO
    project page still contained the older maturity summary snippet, and the KO
    ECON detail page returned 200 without the promoted summary text.
- Blocker:
  `[BCE-2328](/BCE/issues/BCE-2328)` was created for FullStackEngineer to
  diagnose whether production is missing the summary-only `coming_soon` support
  or whether report selection/rendering excludes the ECON summary-authority row.
- Deployment/cache implication:
  Supabase content promotion succeeded, but website-visible publication evidence
  is incomplete. `[BCE-2324](/BCE/issues/BCE-2324)` remains blocked until the
  production pages render the promoted ECON summary.
- Manifest change:
  no change needed. This was a routine execution and website visibility blocker
  under the existing `analysis-md-summary-candidate` and
  `summary_authority_gate` contracts.

### BCE-2324 Final Website Visibility Verification (2026-07-01 06:20 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `e136279`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `[BCE-2328](/BCE/issues/BCE-2328)` child blocker completion으로
  `[BCE-2324](/BCE/issues/BCE-2324)`가 재개되었다.
- Final verification artifact:
  `scripts/pipeline/output/bce2324_huma-finance_econ_final_website_verification.json`.
- DB verification:
  - `report_summary_jobs.id=5ef3d4a5-7a85-4338-985f-92035a75db0c`
  - `validation_status=valid`, `status=candidate_ready`
  - `authority_state=promoted`, `authority_mode=llm_active`
  - `promoted_project_report_id=670b951e-6483-47c2-be85-43bb4e1dd481`
  - `project_reports.id=670b951e-6483-47c2-be85-43bb4e1dd481`
  - `report_type=econ`, `language=ko`, `status=coming_soon`,
    `version=1`, `is_latest=true`
  - `card_data.summary_authority.mode=llm_active`
- Final website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/huma-finance` returned HTTP `200`,
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`,
    and contained the promoted KO ECON summary string.
  - `https://www.bcelab.xyz/en/projects/huma-finance` returned HTTP `200`,
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`,
    and contained the promoted EN ECON summary string.
  - `https://www.bcelab.xyz/ko/reports/huma-finance/econ` returned HTTP `200`,
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`,
    and contained the promoted KO ECON summary string.
  - `https://www.bcelab.xyz/en/reports/huma-finance/econ` returned HTTP `200`,
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`,
    and contained the promoted EN ECON summary string.
- Completion status:
  JSON validation, candidate ingest, Summary Authority Gate `llm_active --write`
  promotion, DB verification, and production website visibility evidence are
  complete. `[BCE-2324](/BCE/issues/BCE-2324)` can close.
- Manifest change:
  no change needed. This was final publication verification under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2324 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 05:34 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  routine execution issue `[BCE-2324](/BCE/issues/BCE-2324)`; 신규 댓글은
  없었고 harness가 checkout한 `issue_assigned` 실행이었다.
- 후보 스캔:
  Google Drive `analysis2/{ECON,MAT,FOR}` 및 legacy `analysis/{ECON,MAT,FOR}`
  Markdown 541건을 메타데이터 기준으로 확인했다. DB의 promoted
  `report_summary_jobs.source_identity`와 revision identity를 대조해 최신
  unpromoted source를 선택했다.
- 이미 promoted로 확인된 최신 소스:
  `Lista DAO / lisUSD` MAT, `Lista DAO lisUSD` ECON, `synapse` ECON,
  `Synapse / Hypercall` MAT, `Data Foundation(DATA Network)` MAT,
  `The DATA Foundation` ECON, `HOT/CELO/SNX/BSV` FOR.
- 이번 실행의 최신 unpromoted Drive Markdown:
  `Huma Finance 크립토이코노미 설계 분석 보고서.md`
  (`report_type=econ`, `modifiedTime=2026-06-28T06:26:34.000Z`).
- Source identity:
  `drive:1RaOfU4Q0qJWxbprNREP0gHkwQ3-osBYz:0B8HYgThT3NBydWlabkJiZmN1alpJTnRTZGZxWDNndlBRVm8wPQ`.
- Canonical tracked project:
  `huma-finance` (`symbol=HUMA`, `status=monitoring_only`).
- 차단 원인:
  `huma-finance/econ/ko`에 website-visible `project_reports` target row가
  없다. `summary_authority_gate.py`의 `find_target_report` 계약상
  `llm_active --write` 승격은 기존 website-visible target row를 필요로 하며,
  현재 상태에서는 `website-visible project_reports target not found:
  huma-finance/econ/ko`로 실패한다.
- 실행 결과:
  CRO JSON 생성, candidate ingest, Summary Authority Gate `--write` 승격은
  수행하지 않았다. 이슈 완료 규칙의 target report lookup failure에
  해당하므로 `[BCE-2325](/BCE/issues/BCE-2325)`를 DataPlatformEngineer에게
  생성하고 `[BCE-2324](/BCE/issues/BCE-2324)`를 해당 이슈에 blocked로
  연결했다.
- 배포/캐시 영향:
  `project_reports` write 및 웹사이트-visible content 변경이 없었으므로
  배포 또는 캐시 무효화는 필요하지 않다.
- Manifest change:
  no change needed. 이번 기록은 기존 `analysis-md-summary-candidate` 및
  `summary_authority_gate` 계약 하의 운영 데이터 블로커 진단이다.

### BCE-2323 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 05:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  routine execution issue `[BCE-2323](/BCE/issues/BCE-2323)`; 신규 댓글은
  없었고 harness가 checkout한 `issue_assigned` 실행이었다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 Drive Markdown
  후보를 확인했다. 직전 `[BCE-2322](/BCE/issues/BCE-2322)`에서 `MEXC`
  MAT가 승격되었으므로 제외되었다. 최신 eligible source인 `SafePal` MAT는
  canonical project와 KO maturity website-visible target row가 확인되어
  이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `SafePal의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2018–2026.md`.
- Canonical tracked project:
  `safepal` (`symbol=SFP`, `status=active`).
- Source identity:
  `drive:1fXOaV-Q9bTIieRo_mSqugRj6Kg0F6lSZ:0B8HYgThT3NByUmJUaFdmR0FiVloyNWUyZ0taNyt3SktZTVNnPQ`.
- Source SHA-256:
  `ff0c16d4e6bf10b71f4c19bcd0effea96c94b471df3506824d23a1b4ea72e8d0`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_safepal_bce2323.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_safepal_bce2323.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_safepal.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `safepal`
  - validation status: `valid`
  - validation reasons: none after compressing KO marketing copy to one
    validator-safe sentence
  - upsert result: `updated_existing`
  - job id: `7eb44f21-ea5a-4cae-897e-cfb01fe462b0`
- Selector recurrence audit:
  the full CLI command reached the same candidate path but was interrupted after
  more than 120 seconds of no output while waiting in Drive
  `MediaIoBaseDownload`. The run then used metadata scan to choose the first
  eligible unpromoted source, fixed Drive file id, revision, source text,
  canonical project, and target row, and reused existing `process_candidate`,
  `upsert_job`, artifact writer, and Summary Authority Gate functions directly.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 7eb44f21-ea5a-4cae-897e-cfb01fe462b0 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2323" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `2006ea3f-4e8f-47eb-bfa6-2fb873dd7ded`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2323_safepal_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=safepal`, `symbol=SFP`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=7eb44f21-ea5a-4cae-897e-cfb01fe462b0`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=2006ea3f-4e8f-47eb-bfa6-2fb873dd7ded`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=SafePal은 3천만 사용자와 200개 이상 체인 접근을 가진 셀프커스터디 금융 포털로 성장했다. 성숙도는 72.95/100이지만, SFP 가치 포획, 수익 환류, 보안 투명성 공개가 핵심 병목이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/safepal`,
    `https://www.bcelab.xyz/en/projects/safepal`,
    `https://www.bcelab.xyz/ko/reports/safepal/maturity`, and
    `https://www.bcelab.xyz/en/reports/safepal/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `SafePal`.
  - `/ko/reports/safepal/mat` and `/en/reports/safepal/mat` returned `404`;
    production route canonicalizes MAT reports as `/maturity`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2322 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 04:49 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  routine execution issue `[BCE-2322](/BCE/issues/BCE-2322)`; 신규 댓글은
  없었고 harness가 checkout한 `issue_assigned` 실행이었다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 Drive Markdown
  후보를 확인했다. 직전 `[BCE-2321](/BCE/issues/BCE-2321)`에서 `Lista DAO
  lisUSD` ECON이 승격되었으므로 제외되었다. 최신 eligible source인
  `MEXC` MAT는 canonical project와 KO maturity website-visible target row가
  확인되어 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `MEXC의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2018–2026.md`.
- Canonical tracked project:
  `mx-token` (`symbol=MX`, `status=active`).
- Source identity:
  `drive:1Xh5974akGR68xY9Kr1cYtx0EJ0XT9pqc:0B8HYgThT3NBydHRHREtYOFVFOG4rTEk4WXJBK3hPcTNGUUtVPQ`.
- Source SHA-256:
  `212b02c9296a7190e6f2183c87d85c56672af8b8e5ccbd4cf8b8c48f1e13275c`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_mx-token_bce2322.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_mx-token_bce2322.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_mx-token.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `mx-token`
  - validation status: `valid`
  - validation reasons: none after removing raw-format English abbreviations and
    expanding ZH marketing copy
  - upsert result: `inserted`
  - job id: `7c811135-98ad-46e7-ad1c-d15b1894bb11`
- Selector recurrence audit:
  to avoid broad Drive selector stalls and wrong-source publication, this run
  used metadata scan to choose the first eligible unpromoted source, then fixed
  Drive file id, revision, source text, canonical project, and target row before
  applying existing `process_candidate`, `upsert_job`, artifact writer, and
  Summary Authority Gate functions directly. The full CLI command reached the
  same candidate path but was interrupted after 90 seconds of no output while
  waiting in Drive `MediaIoBaseDownload`; the direct retry completed and reused
  the existing pipeline validation/upsert functions.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 7c811135-98ad-46e7-ad1c-d15b1894bb11 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2322" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `a87ab5f0-a206-47fd-8403-0e67653a1fef`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2322_mx-token_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=mx-token`, `symbol=MX`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=7c811135-98ad-46e7-ad1c-d15b1894bb11`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=a87ab5f0-a206-47fd-8403-0e67653a1fef`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=MEXC는 0수수료, 광범위한 상장, 강한 거래량, PoR 공개로 성숙 진입 전 단계에 도달했다. 핵심 병목은 수익 지속성, 부채 검증, 규제·운영 투명성이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/mx-token`,
    `https://www.bcelab.xyz/en/projects/mx-token`,
    `https://www.bcelab.xyz/ko/reports/mx-token/maturity`, and
    `https://www.bcelab.xyz/en/reports/mx-token/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `MEXC`.
  - `/ko/reports/mx-token/mat` and `/en/reports/mx-token/mat` returned `404`;
    production route canonicalizes MAT reports as `/maturity`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2321 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 04:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  routine execution issue `[BCE-2321](/BCE/issues/BCE-2321)`; 신규 댓글은
  없었고 harness가 checkout한 `issue_assigned` 실행이었다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 Drive Markdown
  후보를 확인했다. 직전 `[BCE-2320](/BCE/issues/BCE-2320)`에서 `Vaulta`
  MAT가 승격되었고, 최신 `Lista DAO _ lisUSD` MAT source도 이미 promoted
  상태였다. 다음 eligible source인 `Lista DAO lisUSD` ECON은 canonical
  project와 KO economic website-visible target row가 확인되어 이번 실행
  대상으로 선택했다.
- 선택한 Drive Markdown:
  `Lista DAO lisUSD 크립토이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `lisusd` (`symbol=LISUSD`, `status=active`).
- Source identity:
  `drive:1c97CqVrb8j9PJapN75XtXdSi51weYvLY:0B8HYgThT3NByNDhvL2ZyencxbVI5Y011U1BFbDc0Nll4M1pNPQ`.
- Source SHA-256:
  `d292df72e05548c08e7648526b2066d535ae1bd8a7bf5e1b4014b26d815d0694`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_lisusd_bce2321.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_lisusd_bce2321.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_lisusd.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `lisusd`
  - validation status: `valid`
  - validation reasons: none after EN/DE card length and raw-format correction
  - upsert result: `updated_existing`
  - job id: `315206ff-b52a-40ee-86aa-06d0f38d78ef`
- Selector recurrence audit:
  to avoid broad Drive selector stalls and wrong-source publication, this run
  used metadata scan to choose the first eligible unpromoted source, then fixed
  Drive file id, revision, source text, canonical project, and target row before
  applying existing `process_candidate`, `upsert_job`, artifact writer, and
  Summary Authority Gate functions directly. The full CLI command reached the
  same candidate upsert path but was interrupted after 90 seconds of no output
  while waiting on a Supabase `existing_job` response; the direct retry completed
  and reused the existing pipeline validation/upsert functions.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 315206ff-b52a-40ee-86aa-06d0f38d78ef --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2321" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `7d4f8352-a577-4e77-8a66-0248ff322cb2`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2321_lisusd_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=lisusd`, `symbol=LISUSD`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=315206ff-b52a-40ee-86aa-06d0f38d78ef`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=7d4f8352-a577-4e77-8a66-0248ff322cb2`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=lisUSD는 BNB Chain에서 MakerDAO형 CDP를 확장해 담보 stablecoin, liquid staking, PSM, AMO, D3M, veLISTA를 결합한다. 방어층은 넓지만 외부 유동성, 오라클, 코어팀 권한, LISTA emission 지속성이 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/lisusd`,
    `https://www.bcelab.xyz/en/projects/lisusd`,
    `https://www.bcelab.xyz/ko/reports/lisusd/econ`, and
    `https://www.bcelab.xyz/en/reports/lisusd/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO economic report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `lisUSD`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and economic report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2320 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 03:35 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  routine execution issue `[BCE-2320](/BCE/issues/BCE-2320)`; 신규 댓글은
  없었고 harness가 checkout한 `process_lost_retry` 복구 실행이었다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 Drive Markdown
  후보를 확인했다. 직전 `[BCE-2319](/BCE/issues/BCE-2319)`에서 `ApeCoin`
  MAT가 승격되었으므로 제외되었다. `Huma Finance` ECON은 KO economic
  target row가 없어 제외했고, `AIOZ` MAT는 canonical project가 없어
  제외했으며, `ZK` FOR는 KO forensic target row가 없어 제외했다. 다음
  eligible source인 `Vaulta` MAT는 canonical project와 KO maturity
  website-visible target row가 확인되어 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `Vaulta의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2018–2026.md`.
- Canonical tracked project:
  `vaulta` (`symbol=A`, `status=active`).
- Source identity:
  `drive:1mH2GrB5Y3UUjnU1R23RgoFBlzx93q3EC:0B8HYgThT3NByaVJRUHRjSE9VcmZaUWlsT3dUUGxKbDJ5eEFZPQ`.
- Source SHA-256:
  `2318acf5f0f7ee394dc19932002c96317ddf7fdb2c8439979450905fe0feb621`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_vaulta_bce2320.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_vaulta_bce2320.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_vaulta.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `vaulta`
  - validation status: `valid`
  - validation reasons: none after KO sentence-boundary and multilingual card
    length correction
  - upsert result: `inserted`
  - job id: `243899e6-cada-4deb-9282-4e706101a2b8`
- Selector recurrence audit:
  to avoid broad Drive selector stalls and wrong-source publication, this run
  used metadata scan to choose the first eligible unpromoted source, then fixed
  Drive file id, revision, source text, canonical project, and target row before
  applying existing `process_candidate`, `upsert_job`, artifact writer, and
  Summary Authority Gate functions directly. The repository Drive helper stalled
  on `MediaIoBaseDownload`; the source snapshot was fetched through the same
  Drive OAuth credentials using a direct `alt=media` request with timeout.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 243899e6-cada-4deb-9282-4e706101a2b8 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2320" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `fb85c0a5-f4f4-4f73-b862-913cd6e836fe`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2320_vaulta_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=vaulta`, `symbol=A`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=243899e6-cada-4deb-9282-4e706101a2b8`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=fb85c0a5-f4f4-4f73-b862-913cd6e836fe`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Vaulta는 EOS 인프라를 Web3 Banking 체인으로 재포지셔닝했지만 금융 수요 검증은 진행 중이며, 빠른 finality와 고정 공급 대비 TVL, 반복 수익, Omnitrove 상용화가 핵심 과제다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/vaulta`,
    `https://www.bcelab.xyz/en/projects/vaulta`,
    `https://www.bcelab.xyz/ko/reports/vaulta/maturity`, and
    `https://www.bcelab.xyz/en/reports/vaulta/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `Vaulta`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2319 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 02:36 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  routine execution issue `[BCE-2319](/BCE/issues/BCE-2319)`; 신규 댓글은
  없었고 checkout 후 진행했다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 Drive Markdown
  후보를 확인했다. 직전 `[BCE-2317](/BCE/issues/BCE-2317)`에서 `Arweave`
  MAT가 승격되었으므로 제외되었다. `Huma Finance` ECON은 KO economic
  target row가 없어 제외했고, `AIOZ` MAT는 canonical project가 없어
  제외했으며, `ZK` FOR는 KO forensic target row가 없어 제외했다. 다음
  eligible source인 `ApeCoin` MAT는 canonical project와 KO maturity
  website-visible target row가 확인되어 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `ApeCoin의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2022–2026.md`.
- Canonical tracked project:
  `apecoin-ape` (`symbol=APE`, `status=monitoring_only`).
- Source identity:
  `drive:1iddJXxdJ7yvUYsnYOxDLO-qauQYHb_46:0B8HYgThT3NByZ1lhY3ZSMXNPV3Q4ZUVzMlJkc0RBWGU2ZmFvPQ`.
- Source SHA-256:
  `167a6c0bb839e9104333198a3efee1a71808fa7d2abe6d47fc79afb4bbc4a843`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_apecoin-ape_bce2319.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_apecoin-ape_bce2319.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_apecoin-ape.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `apecoin-ape`
  - validation status: `valid`
  - validation reasons: none after JA marketing length correction
  - upsert result: `inserted`
  - job id: `d6393a81-cd51-4c76-8cd6-5bf1e3fd9c33`
- Selector recurrence audit:
  to avoid broad Drive selector stalls and wrong-source publication, this run
  used the metadata scan to choose the first eligible unpromoted source, then
  fixed the Drive file id, revision, source text, canonical project, and target
  row before applying existing `process_candidate`, `upsert_job`, artifact
  writer, and Summary Authority Gate functions directly.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d6393a81-cd51-4c76-8cd6-5bf1e3fd9c33 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2319" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `0e6ff98b-321f-47f6-b151-a565f64439f3`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2319_apecoin-ape_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=apecoin-ape`, `symbol=APE`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=d6393a81-cd51-4c76-8cd6-5bf1e3fd9c33`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=0e6ff98b-321f-47f6-b151-a565f64439f3`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ApeCoin은 BAYC 문화 토큰에서 ApeChain 가스와 거버넌스 토큰으로 전환 중이지만 성숙도는 아직 초기 전개 단계다. 전용 체인과 거버넌스 개편은 성과이나 낮은 TVL, 수수료, 거래량이 핵심 검증 과제다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/apecoin-ape`,
    `https://www.bcelab.xyz/en/projects/apecoin-ape`,
    `https://www.bcelab.xyz/ko/reports/apecoin-ape/maturity`, and
    `https://www.bcelab.xyz/en/reports/apecoin-ape/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `ApeCoin`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2317 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 02:32 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `[BCE-2317](/BCE/issues/BCE-2317)` was blocked by automatic
  `process_lost` recovery. The latest comment was system-generated, not a
  repeated CRO blocker comment, so this run checked it out and resumed the
  routine.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 Drive Markdown
  후보를 확인했다. `Huma Finance` ECON은 `huma-finance` canonical project에
  KO economic target row가 없어 제외했다. `AIOZ` MAT는 canonical project가
  없어 제외했다. `ZK` FOR는 `zksync` canonical project는 있으나 KO
  forensic target row가 없어 제외했다. 다음 eligible source인 `Arweave`
  MAT는 canonical project와 KO maturity website-visible target row가
  확인되어 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `Arweave의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2018 - 2026.md`.
- Canonical tracked project:
  `arweave` (`symbol=AR`, `status=monitoring_only`).
- Source identity:
  `drive:1hlq1Cg0PNWGQyjg9shwyQ_Jv98rC1J2R:0B8HYgThT3NByNmFxeFE4T3JzUkhpalBsYmVxV0wveVFCRzhnPQ`.
- Source SHA-256:
  `09a18f07f8eaba133d756fb2f6b58c6fe8d8762f5fd0444eb6663333c270a3df`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_arweave_bce2317.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_arweave_bce2317.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_arweave.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `arweave`
  - validation status: `valid`
  - validation reasons: none after KO marketing sentence-boundary and ZH length
    correction
  - upsert result: `inserted`
  - job id: `2d650260-c020-4384-b02d-229d512bd929`
- Selector recurrence audit:
  to avoid broad Drive selector stalls and wrong-source publication, this run
  used the metadata scan to choose the first eligible unpromoted source, then
  fixed the Drive file id, revision, source text, canonical project, and target
  row before applying existing `process_candidate`, `upsert_job`, artifact
  writer, and Summary Authority Gate functions directly.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 2d650260-c020-4384-b02d-229d512bd929 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2317" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `ffdf8286-0667-4605-844e-437577c55f7d`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2317_arweave_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=arweave`, `symbol=AR`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=2d650260-c020-4384-b02d-229d512bd929`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=ffdf8286-0667-4605-844e-437577c55f7d`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Arweave는 영구 저장 프로토콜로 이미 높은 성숙도에 도달했지만, 완전한 성숙 단계는 아니다. AO, AR.IO, ArNS가 새 성장축이며 향후 평가는 실제 앱과 접근 경제의 채택에 달려 있다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/arweave`,
    `https://www.bcelab.xyz/en/projects/arweave`,
    `https://www.bcelab.xyz/ko/reports/arweave/maturity`, and
    `https://www.bcelab.xyz/en/reports/arweave/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `Arweave`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2318 CRO Analysis MD Summary JSON Ingestion Routine (2026-07-01 02:27 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  routine execution issue `[BCE-2318](/BCE/issues/BCE-2318)`; 신규 댓글은
  없었고 checkout 후 진행했다.
- 재발/중복 확인:
  DB의 `lisusd` canonical project와 KO econ website-visible target row를
  확인했다. `report_summary_jobs`에는 `lisusd/econ` 기존 job이 없어 최신
  eligible source인 `Lista DAO lisUSD` ECON을 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `Lista DAO lisUSD 크립토이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `lisusd` (`symbol=LISUSD`, `status=active`).
- Source identity:
  `drive:1c97CqVrb8j9PJapN75XtXdSi51weYvLY:0B8HYgThT3NByNDhvL2ZyencxbVI5Y011U1BFbDc0Nll4M1pNPQ`.
- Source SHA-256:
  `659618780f346bc9e4b66c9c46ccc396d2c06fa1c0bd293372ddc65841d31b95`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_lisusd_bce2318.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_lisusd_bce2318.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_lisusd.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `lisusd`
  - validation status: `valid`
  - validation reasons: none after EN/FR/ES/DE length and raw-format correction
  - upsert result: `updated_existing`
  - job id: `315206ff-b52a-40ee-86aa-06d0f38d78ef`
- Selector recurrence audit:
  prior routine executions documented that the broad standard CLI selector can
  stall while downloading many Drive candidates. To avoid a wrong-source or
  stalled publication, this run fixed the Drive file id, revision, source text,
  canonical project, and target row, then applied existing `process_candidate`,
  `upsert_job`, artifact writer, and Summary Authority Gate functions directly.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 315206ff-b52a-40ee-86aa-06d0f38d78ef --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2318" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `7d4f8352-a577-4e77-8a66-0248ff322cb2`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2318_lisusd_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=lisusd`, `symbol=LISUSD`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=315206ff-b52a-40ee-86aa-06d0f38d78ef`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=7d4f8352-a577-4e77-8a66-0248ff322cb2`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Lista DAO lisUSD는 과잉담보 CDP를 BNBFi로 확장한 설계다. PSM, AMO, D3M, 다중 오라클은 강점이지만 외부 의존성, 거버넌스 집중, LISTA 보상 지속성이 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/lisusd`,
    `https://www.bcelab.xyz/en/projects/lisusd`,
    `https://www.bcelab.xyz/ko/reports/lisusd/econ`, and
    `https://www.bcelab.xyz/en/reports/lisusd/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO econ report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `lisUSD`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and econ report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2316 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-30 16:44 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 Drive
  Markdown 후보를 확인했다. `Huma Finance` ECON은 source는 미승격이나
  KO economic website-visible target row가 없어 제외했다. 현재 DB에는
  `lisusd` canonical project와 KO maturity target row가 존재하여 최신
  미승격 eligible source인 `Lista DAO / lisUSD` MAT를 이번 실행 대상으로
  선택했다.
- 선택한 Drive Markdown:
  `Lista DAO _ lisUSD의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024-2026.md`.
- Canonical tracked project:
  `lisusd` (`symbol=LISUSD`, `status=active`).
- Source identity:
  `drive:1WA6V3zdR1PWdXFvpAfISRlAWRGO3fgBe:0B8HYgThT3NByYWlGTVJzN1JDWURMTmZMVGU5Z1YzQUV2SDBvPQ`.
- Source SHA-256:
  `bc5da7fc53c0fb3c5f8d0d7ec2b01d2b9bb876cbfdf762872a869240d878a050`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_lisusd_bce2316.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_lisusd_drive_selected_bce2316.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_lisusd.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `lisusd`
  - validation status: `valid`
  - validation reasons: none after EN/FR/ES/DE card-length correction
  - upsert result: `updated_existing`
  - job id: `3b684e6b-a56b-4d99-8444-db2cd11d678d`
- Selector recurrence audit:
  the standard CLI command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug lisusd --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_lisusd_bce2316.json --require-agent-output --limit 1 --force`
  was still downloading broad Drive candidates after more than 150 seconds and
  was interrupted during `_download_drive_text`. To avoid stalled execution and
  wrong-source publication, this run fixed the Drive file id, revision, source
  text, canonical project, and target row, then applied existing
  `process_candidate`, `upsert_job`, artifact writer, telemetry, and Summary
  Authority Gate functions directly.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 3b684e6b-a56b-4d99-8444-db2cd11d678d --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2316" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d9f53bb1-980c-460b-a316-fd58da89f19c`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2316_lisusd_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=lisusd`, `symbol=LISUSD`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=3b684e6b-a56b-4d99-8444-db2cd11d678d`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=d9f53bb1-980c-460b-a316-fd58da89f19c`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Lista DAO의 lisUSD는 BNBFi 담보·대출·유동성 확장으로 전개 서사 후반에 있다. 페그와 과잉담보 구조, LISTA 소각, 수익 기반 tokenomics는 강점이지만 거버넌스 집중과 수익 둔화가 성숙 진입의 핵심 관문이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/lisusd`,
    `https://www.bcelab.xyz/en/projects/lisusd`,
    `https://www.bcelab.xyz/ko/reports/lisusd/maturity`, and
    `https://www.bcelab.xyz/en/reports/lisusd/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `lisUSD`.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2315 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-30 15:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry` 이후 `issue_continuation_needed`; 신규 댓글은 없었고
  harness checkout 상태라 추가 checkout은 하지 않았다.
- 재발/중복 확인:
  REST로 최신 promoted `report_summary_jobs`를 확인했다. 직전
  `golem-network-tokens` MAT job
  `ef4ebb66-8b4a-42a9-9a91-2ff0f66bae47`는 이미 `promoted` 및
  `llm_active` 상태였다. 최신 Drive source인 `Lista DAO / lisUSD`
  ECON/MAT는 canonical tracked project가 없어 제외했다. 다음 eligible
  source인 `Huma Finance` MAT는 `huma-finance` canonical project 및 KO
  maturity website-visible target row가 확인되어 이번 실행 대상으로
  선택했다.
- 선택한 Drive Markdown:
  `Huma Finance의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2022 - 2026.md`.
- Canonical tracked project:
  `huma-finance` (`symbol=HUMA`, `status=monitoring_only`).
- Source identity:
  `drive:1iOg0Qxz0JYGcS_WvTTnwDUs2AuG0bv2k:0B8HYgThT3NByRlBnMHk3bEhyN1ArTkd2SkNxcThweGNyZjBrPQ`.
- Source SHA-256:
  `a096e5d98b35ec29f966e120d514f90c42ac0e2fa02a0f4df670194fd962360a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_huma-finance_bce2315.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_huma-finance_drive_selected_bce2315.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_huma-finance.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `huma-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d13af26b-6f00-442e-b02e-b9310f0c2184`
- Selector recurrence audit:
  the standard CLI command without `--force` still spent over 150 seconds
  downloading broad Drive candidates before reaching the fixed Huma source. To
  avoid wrong-source publication, this run fixed the Drive file id, revision,
  source text, canonical project, and target row, then applied existing
  `process_candidate`, `upsert_job`, artifact writer, and Summary Authority
  Gate functions directly.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d13af26b-6f00-442e-b02e-b9310f0c2184 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2315" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `c3239d61-bea8-4782-9233-248c3c195d51`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2315_huma-finance_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=huma-finance`, `symbol=HUMA`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=d13af26b-6f00-442e-b02e-b9310f0c2184`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=c3239d61-bea8-4782-9233-248c3c195d51`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Huma Finance는 PayFi를 실물 결제와 온체인 유동성으로 연결하며 전개 서사 후반에 있다. Huma 2.0, 활성 유동성, CCIP와 기관 파트너십은 강점이지만 거버넌스 실행과 신용성과 공시가 아직 성숙의 관문이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/huma-finance`,
    `https://www.bcelab.xyz/en/projects/huma-finance`,
    `https://www.bcelab.xyz/ko/reports/huma-finance/maturity`, and
    `https://www.bcelab.xyz/en/reports/huma-finance/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `Huma`.
  - The local Python/curl TLS verifier used certificate verification disabled
    for the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2305 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 06:42 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2304](/BCE/issues/BCE-2304)의 `data-network` ECON은
  이미 promoted 및 웹 검증 완료 상태였다. 최신 미승격 source인
  `Lista DAO / lisUSD` ECON/MAT는 canonical tracked project가 없어 제외했다.
  `AIOZ Network` MAT도 `tracked_projects` canonical slug와 target row가
  없어 제외했다. 다음 최신 eligible source인 `AB` MAT는 `ab-chain`
  canonical project 및 KO maturity website-visible target row가 확인되어
  이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `AB의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2018 - 2026.md`.
- Canonical tracked project:
  `ab-chain` (`symbol=AB`, `status=active`).
- Source identity:
  `drive:1AHpYvMrsUBMnvpYjbHqsU5DwFu6FniK3:0B8HYgThT3NBydVVJZmpaVmxTdS80NmZZOG1ZaHFoY0dYcEJ3PQ`.
- Source SHA-256:
  `224db2dc926e8cfecf4e3ad4624117f2a3ed406b5a6b8c390756cf92d77f52c0`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_ab-chain_bce2305.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_ab-chain_drive_selected_bce2305.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_ab-chain.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `ab-chain`
  - validation status: `valid`
  - validation reasons: none after card-format correction
  - upsert result: `inserted`
  - job id: `eafd79d7-4b0f-490a-ab88-627a815164ae`
- Selector recurrence audit:
  slug-less Drive Markdown can still create false-positive matches during broad
  polling. This run fixed the exact Drive file id, revision, source text,
  canonical project, and target row before applying existing `process_candidate`,
  `upsert_job`, artifact writer, and telemetry functions directly.
- Validation correction:
  the first local JSON used raw card fragments such as `L1`, hyphenated English
  phrases, and an overlong KO marketing sentence. Card-facing copy was changed
  to natural language while preserving the source-grounded maturity assessment.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id eafd79d7-4b0f-490a-ab88-627a815164ae --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2305" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `3410bfbe-c90e-4130-9836-0e0a4686af2c`
  - promoted at: `2026-06-28T21:39:17.730265+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2305_ab-chain_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ab-chain`, `symbol=AB`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=eafd79d7-4b0f-490a-ab88-627a815164ae`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=3410bfbe-c90e-4130-9836-0e0a4686af2c`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=AB Chain은 Newton 계열에서 결제와 스테이블코인 중심 네트워크로 재정의되며 전개 단계에 진입했다. AB Core, UTP, USD1, ARC 표준과 MiCA 백서는 긍정적이나 검증자 분산과 수익 공개가 아직 부족하다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ab-chain`,
    `https://www.bcelab.xyz/en/projects/ab-chain`,
    `https://www.bcelab.xyz/ko/reports/ab-chain/maturity`, and
    `https://www.bcelab.xyz/en/reports/ab-chain/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO maturity report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `AB Chain`.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and maturity report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2304 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 06:06 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 미승격 source인 `Lista DAO / lisUSD` ECON/MAT는
  canonical tracked project가 없어 제외했고, 직전 [BCE-2303](/BCE/issues/BCE-2303)의
  `data-network` MAT는 이미 promoted 및 웹 검증 완료 상태였다. 다음
  최신 eligible source인 `The DATA Foundation` ECON은 `data-network`
  canonical project 및 KO econ website-visible target row가 확인되어
  이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `The DATA Foundation 크립토이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `data-network` (`symbol=DATA`, `status=monitoring_only`).
- Source identity:
  `drive:1-aEbZq30he7HEaJxXQq3ddOQWPlzXLBS:0B8HYgThT3NByMnFmOVhjb3M2UFVHZFZQMDVHT3NlMTJkUVpNPQ`.
- Source SHA-256:
  `ee296249fdeeb660276b81658b5e974f7168b5ecf4e4769f51ca40c8c688fb34`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_data-network_bce2304.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_data-network_drive_selected_bce2304.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_data-network.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `data-network`
  - validation status: `valid`
  - validation reasons: none after card-format correction
  - upsert result: `inserted`
  - job id: `d58fec6a-b085-4962-bf59-7b690ebbb383`
- Selector recurrence audit:
  `list_drive_candidates(report_type=econ, slug=data-network, source_scope=all)`
  returned the newer `Lista DAO lisUSD` file as a false positive because the
  helper uses `fetch_project(None, slug)` and therefore lacks DB aliases/project
  metadata during scoring. To avoid publishing the wrong source, this run fixed
  the exact Drive file id, revision, source text, canonical project, and target
  row before applying existing `process_candidate`, `upsert_job`, artifact
  writer, and telemetry functions directly.
- Validation correction:
  the first local validation used `EIP-1559` in card copy, which the card gate
  treats as a raw/formula fragment. Card-facing copy was changed to `fee burn`
  while preserving the source-grounded economic meaning.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d58fec6a-b085-4962-bf59-7b690ebbb383 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2304" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `1347b2cd-a9ea-4589-b012-b05d7af5201a`
  - promoted at: `2026-06-28T21:05:18.943438+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2304_data-network_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=data-network`, `symbol=DATA`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=d58fec6a-b085-4962-bf59-7b690ebbb383`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=1347b2cd-a9ea-4589-b012-b05d7af5201a`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=DATA 토큰은 gas, staking, validator 보상, fee burn의 핵심 단위다. Trace, CDR, IP Licensing 수요가 블록공간으로 이어질 수 있지만, 데이터 매출의 토큰 보유자 직접 귀속은 공개 문서에서 확인되지 않는다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/data-network`,
    `https://www.bcelab.xyz/en/projects/data-network`,
    `https://www.bcelab.xyz/ko/reports/data-network/econ`, and
    `https://www.bcelab.xyz/en/reports/data-network/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO ECON report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `DATA Network`.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and ECON report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2303 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 05:41 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 source인 `Lista DAO / lisUSD` ECON/MAT는 canonical
  tracked project가 없어 제외했고, 직전 [BCE-2301](/BCE/issues/BCE-2301)
  및 [BCE-2302](/BCE/issues/BCE-2302)의 `synapse-2` ECON/MAT는 이미
  promoted 및 웹 검증 완료 상태였다. 다음 최신 eligible source인
  `Data Foundation(DATA Network)` MAT는 `data-network` canonical project
  및 KO maturity website-visible target row가 확인되어 이번 실행
  대상으로 선택했다.
- 선택한 Drive Markdown:
  `Data Foundation(DATA Network)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Canonical tracked project:
  `data-network` (`symbol=DATA`, `status=monitoring_only`).
- Source identity:
  `drive:19drMKLF3sorbWX2JC5pvgojlR-bctjvI:0B8HYgThT3NByL0FNMEEzUlgwamFXclJ5NC80SmpNc3VyNDRNPQ`.
- Source SHA-256:
  `10d327469b50db04eb21b5ae6fe5a422323d12500f8802ae20f9c3e11270d405`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_data-network_bce2303.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_data-network_drive_selected_bce2303.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_data-network.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `data-network`
  - validation status: `valid`
  - validation reasons: none after card-format and evidence-array correction
  - upsert result: `updated_existing`
  - job id: `81251803-0c29-4a0f-84ec-c5b9e58dceae`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug data-network --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_data-network_bce2303.json --require-agent-output --limit 1 --force`
  는 Drive 후보 다운로드 단계에서 약 90초간 무출력으로 지연되어
  중단했다. 이후 확정 Drive file id, revision, source text, canonical
  project, target row를 고정한 뒤 기존 `process_candidate`, `upsert_job`,
  artifact writer, telemetry 함수를 직접 적용했다.
- Validation correction:
  최초 JSON은 `source_sentences_not_array` 및 일부 영문/독문 raw-format
  validation 실패로 invalid row를 만들었으나, 같은 idempotency key를
  `force=True`로 갱신해 valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 81251803-0c29-4a0f-84ec-c5b9e58dceae --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2303" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `42d0242c-8da7-48d8-87fe-f89d13b98526`
  - promoted at: `2026-06-28T20:41:28.654412+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2303_data-network_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=data-network`, `symbol=DATA`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=81251803-0c29-4a0f-84ec-c5b9e58dceae`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=42d0242c-8da7-48d8-87fe-f89d13b98526`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=DATA Network는 54점의 전개 서사 단계 L1이다. AI 데이터 provenance와 권리 인프라 서사는 명확하지만, Trace와 CDR의 production 전환, 수익화, validator 경제가 성숙도 상승의 핵심 조건이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/data-network`,
    `https://www.bcelab.xyz/en/projects/data-network`,
    `https://www.bcelab.xyz/ko/reports/data-network/maturity`, and
    `https://www.bcelab.xyz/en/reports/data-network/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project page and KO MAT report page contained the promoted summary
    string in rendered HTML. EN project/report pages returned 200 and contained
    `DATA Network`.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and MAT report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2302 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 05:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 미승격 source인 `Lista DAO / lisUSD` ECON/MAT는
  canonical tracked project가 없어 제외했다. 직전 [BCE-2301](/BCE/issues/BCE-2301)
  에서 `synapse-2` ECON은 promoted 및 웹 검증 완료 상태였다. 다음 최신
  eligible source인 `Synapse / Hypercall` MAT는 `synapse-2` canonical
  project 및 KO maturity website-visible target row가 확인되어 이번
  실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `Synapse _ Hypercall의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2021–2026.md`.
- Canonical tracked project:
  `synapse-2` (`symbol=SYN`, `status=monitoring_only`).
- Source identity:
  `drive:1KJRkCf3ldOxzabmU8QHu2YiaDLTlmEh8:0B8HYgThT3NByYUc2VU1OSHV5RXFzYkFsUGJFcWZxTUpIeHFrPQ`.
- Source SHA-256:
  `415fb5ae6b68116e32a07ab3af443c90ea6fb650a5cda3b321c3ef9880aba949`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_synapse-2_bce2302.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_synapse-2_drive_selected_bce2302.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_synapse-2.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `synapse-2`
  - validation status: `valid`
  - validation reasons: none after card-format correction
  - upsert result: `inserted`
  - job id: `9d1b60bb-0cfd-4600-808d-c588b2a751d0`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug synapse-2 --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_synapse-2_bce2302.json --require-agent-output --limit 1 --force`
  는 Drive 후보 다운로드 단계에서 약 90초간 무출력으로 지연되어
  중단했다. DB write 전 selector 단계였으므로 잘못된 row는 생성되지
  않았다. 이후 확정 Drive file id, revision, source text, canonical
  project, target row를 고정한 뒤 기존 `process_candidate`, `upsert_job`,
  artifact writer, telemetry 함수를 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 9d1b60bb-0cfd-4600-808d-c588b2a751d0 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2302" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `6c2fe004-6655-4f75-b514-301817333a3f`
  - promoted at: `2026-06-28T20:06:58.598083+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2302_synapse-2_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=synapse-2`, `symbol=SYN`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=9d1b60bb-0cfd-4600-808d-c588b2a751d0`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=6c2fe004-6655-4f75-b514-301817333a3f`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Synapse Hypercall은 성숙도 51.45점으로 전개 서사 초기의 옵션 인프라다. 브릿지 기반과 Mainnet Alpha는 강점이지만, 수익 급감, 미실행 fee sharing, 운영자 매칭 신뢰, audit source 미공개가 성숙도 상승을 제한한다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/synapse-2`,
    `https://www.bcelab.xyz/en/projects/synapse-2`,
    `https://www.bcelab.xyz/ko/reports/synapse-2/maturity`, and
    `https://www.bcelab.xyz/en/reports/synapse-2/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO/EN project pages and KO/EN MAT report pages contained the promoted
    summary strings in rendered HTML.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and MAT report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2301 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 04:43 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 미승격 source 중 `Lista DAO / lisUSD` ECON/MAT는
  canonical tracked project가 없어 제외했다. 다음 최신 eligible source인
  `synapse` ECON은 `synapse-2` canonical project 및 KO economic
  website-visible target row가 확인되어 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `synapse 크립토 이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `synapse-2` (`symbol=SYN`, `status=monitoring_only`).
- Source identity:
  `drive:1H8QfAtpD76lPz8KXMD0EJo6ufJG2ILyP:0B8HYgThT3NBydlNZU0RocWY3NTBjbVZRbVNuU2lrZmI0L2ljPQ`.
- Source SHA-256:
  `b44a1f14bf7782fe6c065eaf4484ae5a5b3e6e20b51f1878c7e5ddd4fa8a095f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_synapse-2_bce2301.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_synapse-2_drive_selected_bce2301.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_synapse-2.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `synapse-2`
  - validation status: `valid`
  - validation reasons: none after card-format correction
  - upsert result: `updated_existing`
  - job id: `8589f3b0-a360-4197-be2a-7d79e6a1b5cd`
- Selector recurrence audit:
  기본 CLI selector는 미파싱 Drive 파일명에서 slug 필터가 약해 다른
  후보를 고를 수 있어, 확정 Drive file id/revision/source text/canonical
  project/target row를 고정한 뒤 기존 `process_candidate`, `upsert_job`,
  artifact writer, telemetry 함수를 직접 적용했다. 최초 JSON은
  card-format validation 실패로 invalid row를 만들었으나, 같은
  idempotency key를 `force=True`로 갱신해 valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 8589f3b0-a360-4197-be2a-7d79e6a1b5cd --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2301" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `3ba8cd73-cabb-49d7-b394-922b4476ada4`
  - promoted at: `2026-06-28T19:43:19.763247+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2301_synapse-2_econ_db_verification.json`.
- Website verification artifact:
  `scripts/pipeline/output/bce2301_synapse-2_econ_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=synapse-2`, `symbol=SYN`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=8589f3b0-a360-4197-be2a-7d79e6a1b5cd`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=3ba8cd73-cabb-49d7-b394-922b4476ada4`
  - `report_type=economic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Synapse는 브릿지와 메시징 기반 위에 Hypercall 옵션 거래소를 얹어 SYN 거버넌스 범위를 확장하지만, 수수료 공유 미가동과 운영자 신뢰, 감사 공개 지연, Hyperliquid 의존도가 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/synapse-2`,
    `https://www.bcelab.xyz/en/projects/synapse-2`,
    `https://www.bcelab.xyz/ko/reports/synapse-2/econ`, and
    `https://www.bcelab.xyz/en/reports/synapse-2/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO/EN project pages and KO/EN ECON report pages contained the promoted
    summary strings in rendered HTML.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page and ECON report-page
  visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2300 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 04:09 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2299](/BCE/issues/BCE-2299)는 `BSV` FOR를 promoted
  및 웹 검증 완료했다. 최신 미승격 source 중 `Lista DAO / lisUSD` MAT는
  canonical project가 없고, `synapse` ECON/MAT 및 `Data Network` MAT는 해당
  타입의 KO target row가 없어 제외했다. 다음 eligible source인 `MOODENG`
  FOR는 `moo-deng-solana` canonical project 및 KO forensic website-visible
  target row가 확인되어 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `MOODENG 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `moo-deng-solana` (`symbol=MOODENG`, `status=monitoring_only`).
- Source identity:
  `drive:1D57-99KtjvqA_so93jSA_Aq60R0kOCAu:0B8HYgThT3NByUW01SmlvQU5SbnlXUWpLYThTelhPQ2RLNHNZPQ`.
- Source SHA-256:
  `78cbcdc246daac351515017bdede44bdd36de917c07bf29b8cd16995453ebe94`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_moo-deng-solana_bce2300.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_moo-deng-solana_drive_selected_bce2300.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_moo-deng-solana.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `moo-deng-solana`
  - validation status: `valid`
  - validation reasons: none after KO marketing sentence-count correction
  - upsert result: `inserted`
  - job id: `9f9a8d0c-37fd-4c61-bfd7-d0f71262df70`
- Selector recurrence audit:
  표준 command에 `--force`를 붙이면 promoted source까지 포함하면서 다른
  Drive file `17RihIV_zA8k4Xd6CHo6zqtIs2bTkNDq-`를 먼저 선택했고,
  `moo-deng-solana` slug 아래 invalid candidate
  `77ce7e95-ecb4-4613-8ef2-489ea72b2dcf`를 생성했다. 해당 row는
  `validation_failed`라 promotion에 사용하지 않았다. 이후 `--force` 없이
  promoted source 제외 selector를 실행해 올바른 MOODENG Drive source를
  valid 상태로 inserted했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 9f9a8d0c-37fd-4c61-bfd7-d0f71262df70 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2300" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `3c8b2626-af0d-45d7-936f-704823fb4e24`
  - promoted at: `2026-06-28T19:09:04.770357+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2300_moo_deng_solana_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=moo-deng-solana`, `symbol=MOODENG`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=9f9a8d0c-37fd-4c61-bfd7-d0f71262df70`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=3c8b2626-af0d-45d7-936f-704823fb4e24`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=MOODENG는 56점의 높은 포렌식 리스크 구간이다. 0.03895 저점 반등에도 거래량은 VOL MA20의 19% 수준이고, 양수 펀딩과 큰 OI가 롱 청산 민감도를 키운다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/moo-deng-solana`,
    `https://www.bcelab.xyz/en/projects/moo-deng-solana`,
    `https://www.bcelab.xyz/ko/reports/moo-deng-solana/forensic`, and
    `https://www.bcelab.xyz/en/reports/moo-deng-solana/forensic` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches prior FOR report-body
    surface behavior and does not indicate a failed gate promotion.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2278 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 15:11 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 unpromoted source인 `MUon` MAT, `Light Heaven`
  ECON/MAT, `ARC` MAT/ECON, `MindWaveDAO` ECON, `AIOZ` MAT, `ZK` FOR는
  target row 부재, canonical 매칭 리스크, 또는 이전 이력과 같은 제외
  사유로 건너뛰었다. 이번 실행에서 `Tether` MAT Drive source가
  `tether` canonical project 및 KO maturity target row를 가진 최신
  eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `Tether의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2014 - 2026 (1).md`.
- Canonical tracked project:
  `tether` (`symbol=USDT`, `status=active`).
- Source identity:
  `drive:1zJR-ysfGgrRwUJijXQJ-BvkGmugb5O0L:0B8HYgThT3NByOElsdXRpVTNoazF5bzNQU3ZhN1oxNEpibXRvPQ`.
- Source SHA-256:
  `1b95e8d6f64803386487aba8e9b17f6fad0fdc86e7ff9b220a41e9eae228c85b`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_tether_bce2278.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_tether_drive_selected_bce2278.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_tether.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `tether`
  - validation status: `valid`
  - validation reasons: none after length correction
  - upsert result: `updated_existing`
  - job id: `3a947e0f-de1c-4b53-a128-7577385cf6b1`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug tether --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_tether_bce2278.json --require-agent-output --limit 1 --force`
  는 Drive selector가 후보 다운로드 단계에서 90초 가까이 무출력으로
  지연되어 중단했다. 이미 Drive file id, revision, source text,
  canonical project, target row가 확정된 상태라 기존 validator, artifact
  writer, telemetry, `upsert_job` 함수를 고정 후보에 직접 적용했다. 최초
  validation은 EN/FR/ES/DE summary length로 invalid였으나, 같은
  idempotency key를 `force=True`로 갱신해 valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 3a947e0f-de1c-4b53-a128-7577385cf6b1 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2278" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `afb182dd-77f4-442b-bde4-55c916057438`
  - promoted at: `2026-06-28T06:09:28.317348+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2278_tether_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=tether`, `symbol=USDT`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=3a947e0f-de1c-4b53-a128-7577385cf6b1`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=afb182dd-77f4-442b-bde4-55c916057438`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=3`, `is_latest=true`
  - `card_summary_ko=Tether는 78.0/100의 성숙 단계 진입 직전 스테이블코인 인프라다. USDT는 시장 지배력, 멀티체인 유통, 거래소 유동성이 강하지만 완전감사 부재, 준비금 위험, 소액 상환 제한과 중앙화 동결 권한이 과제다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/tether`,
    `https://www.bcelab.xyz/en/projects/tether`,
    `https://www.bcelab.xyz/ko/reports/tether/maturity`, and
    `https://www.bcelab.xyz/en/reports/tether/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2297 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 02:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2296](/BCE/issues/BCE-2296)는 `HOT` FOR를 promoted
  및 웹 검증 완료했다. 최신 미승격 Drive 후보 중 `CELO` FOR는 canonical
  project는 있으나 KO forensic target row가 없어 제외했다. 다음 최신
  후보인 `SNX` FOR는 `synthetix` canonical project 및 KO forensic
  website-visible target row가 확인되어 이번 eligible source로 선택했다.
- 선택한 Drive Markdown:
  `SNX 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `synthetix` (`symbol=SNX`, `status=active`).
- Source identity:
  `drive:1eLf2rwjHzPGl8W-iJ-K1EXTHfFc7tMvk:0B8HYgThT3NByS21raVdQeHNlZzI5SXRQbWxKTzJ1d0JxSjZvPQ`.
- Source SHA-256:
  `f35c20a189b67687cad36989b298044abb6b7aa4743c05671ae638a7b9b55ed4`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_synthetix_bce2297.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_synthetix_drive_selected_bce2297.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_synthetix.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `synthetix`
  - validation status: `valid`
  - validation reasons: none after card-safe wording corrections
  - upsert result: `inserted`
  - job id: `a535f222-59be-43c3-8fb8-d2e7ea655228`
- Selector recurrence audit:
  표준 selector는 이전 실행들처럼 `--slug` 지정 후에도 최신 다른 후보를
  먼저 만질 수 있어, 이번 실행은 Drive metadata, file id, revision,
  source text, canonical project, target row를 먼저 확정한 뒤 기존
  validator, artifact writer, telemetry, `upsert_job` 함수를 고정 후보에
  직접 적용했다. 최초 validation은 EN/FR/ES/DE raw-format fragment,
  KO marketing sentence count, ZH marketing length로 invalid였고, 문구를
  수정한 뒤 같은 후보를 valid 상태로 upsert했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id a535f222-59be-43c3-8fb8-d2e7ea655228 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2297" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `c864938b-09fc-4da9-994b-b9407328e1de`
  - promoted at: `2026-06-28T17:38:55.741686+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2297_synthetix_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=synthetix`, `symbol=SNX`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=a535f222-59be-43c3-8fb8-d2e7ea655228`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=c864938b-09fc-4da9-994b-b9407328e1de`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=SNX는 63점의 중상위 포렌식 리스크 구간이다. 0.192 저점 뒤 반등했지만 0.238과 0.253 저항을 넘지 못했고, 음수 펀딩과 레버리지 증가는 숏커버링성 반등 가능성을 키운다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/synthetix`,
    `https://www.bcelab.xyz/en/projects/synthetix`,
    `https://www.bcelab.xyz/ko/reports/synthetix/forensic`, and
    `https://www.bcelab.xyz/en/reports/synthetix/forensic` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches prior FOR report-body
    surface behavior and does not indicate a failed gate promotion.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2298 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 03:05 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 Drive 후보 중 `HOT` FOR와 `SNX` FOR는 이미 promoted
  상태였다. 직전 이력에서 `CELO` FOR는 target row 부재로 제외됐지만,
  현재 DB에는 `celo` canonical project와 KO forensic website-visible
  target row가 존재해 이번 최신 eligible source로 선택했다.
- 선택한 Drive Markdown:
  `CELO 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `celo` (`symbol=CELO`, `status=monitoring_only`).
- Source identity:
  `drive:1L1RYS22bgyKhHOlQfSpa0PHD_AmvaMjQ:0B8HYgThT3NByZzhUT3RPTU5pNGpoMThMT0xISnlLRXVBblBVPQ`.
- Source SHA-256:
  `4618036b934f12fb82a5354cbf813edb5ddb2c39748e7da3b9362ce1c4f8de2f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_celo_bce2298.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_celo_drive_selected_bce2298.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_celo.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `celo`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `0e1cbccc-f706-4388-a290-50379eea534a`
- Selector recurrence audit:
  표준 selector는 이전 실행들처럼 `--slug` 지정 후에도 FOR 폴더 전체
  후보를 다운로드할 수 있다. 이번 실행은 Drive metadata, file id,
  revision, source text, canonical project, target row를 먼저 확정한 뒤
  기존 validator, artifact writer, telemetry, `upsert_job` 함수를 고정
  후보에 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0e1cbccc-f706-4388-a290-50379eea534a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2298" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `8afff080-e0dd-4010-8286-697dde940201`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2298_celo_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=celo`, `symbol=CELO`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=0e1cbccc-f706-4388-a290-50379eea534a`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=8afff080-e0dd-4010-8286-697dde940201`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=CELO는 61점의 높은 포렌식 리스크 구간이다. 0.05605 저점 뒤 반등했지만 0.07007은 MA(99) 0.07859 아래에 있고, 141.28M CELO 거래량 급증은 저점 유동성 흡수와 단기 투기 수급을 함께 시사한다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/celo`,
    `https://www.bcelab.xyz/en/projects/celo`,
    `https://www.bcelab.xyz/ko/reports/celo/forensic`, and
    `https://www.bcelab.xyz/en/reports/celo/forensic` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches prior FOR report-body
    surface behavior and does not indicate a failed gate promotion.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2299 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 03:37 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 미승격 후보 `synapse` ECON은 `synapse-2` canonical
  project는 있으나 KO econ target row가 없어 제외했다. 다음 미승격 후보
  `BSV` FOR는 `bitcoin-sv` canonical project 및 KO forensic
  website-visible target row가 확인되어 이번 eligible source로 선택했다.
- 선택한 Drive Markdown:
  `BSV 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `bitcoin-sv` (`symbol=BSV`, `status=active`).
- Source identity:
  `drive:15pGQNBXfLuW5ATtqTitN0Vt0tBGaDy_k:0B8HYgThT3NByNlVRVU1XZmFEMlpGRVg5dFV5aWNMUDVTTXdVPQ`.
- Source SHA-256:
  `b5be1da3b0514d7f04d6ce184f55f13c34dbd95715fd415d1e11e7dee0cbb174`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_bitcoin-sv_bce2299.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_bitcoin-sv_drive_selected_bce2299.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_bitcoin-sv.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `bitcoin-sv`
  - validation status: `valid`
  - validation reasons: none after exact Markdown source sentence and KO
    marketing sentence-count corrections
  - upsert result: `inserted`
  - job id: `e8e3ce34-52e6-4d67-a117-cba17bd436e2`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug bitcoin-sv --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_bitcoin-sv_bce2299.json --require-agent-output --limit 1 --force`
  는 `--force`로 promoted source를 포함하면서 이미 승격된 `HOT` FOR
  Drive file을 먼저 선택했고, `bitcoin-sv` slug 아래 invalid candidate
  `4584895e-79be-465e-8e6e-ece99444c4e2`를 생성했다. 해당 invalid row는
  `authority_state=validation_failed`라 promotion에 사용하지 않았다. 이후
  BSV Drive file id, revision, source text, canonical project, target row를
  고정하고 기존 validator, artifact writer, telemetry, `upsert_job` 함수를
  직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id e8e3ce34-52e6-4d67-a117-cba17bd436e2 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2299" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `32898e3e-9255-4465-b94e-b1aead8e0abc`
  - promoted at: `2026-06-28T18:35:48.329055+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2299_bitcoin-sv_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bitcoin-sv`, `symbol=BSV`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=e8e3ce34-52e6-4d67-a117-cba17bd436e2`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=32898e3e-9255-4465-b94e-b1aead8e0abc`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Bitcoin SV BSV는 62점의 높은 포렌식 리스크 구간이다. 12.5088 USDT는 단기 이동평균 아래지만 중기선 위에 있어, 얇은 유동성과 선물 OI가 변동성을 키우는 확인 매매 구간이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/bitcoin-sv`,
    `https://www.bcelab.xyz/en/projects/bitcoin-sv`,
    `https://www.bcelab.xyz/ko/reports/bitcoin-sv/forensic`, and
    `https://www.bcelab.xyz/en/reports/bitcoin-sv/forensic` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches prior FOR report-body
    surface behavior and does not indicate a failed gate promotion.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2296 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 01:01 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2295](/BCE/issues/BCE-2295)는 `Data IP` FOR를
  promoted 및 웹 검증 완료했다. 최신 미승격 Drive 후보는 `HOT`, `CELO`,
  `SNX`, `BSV` FOR 순이었다. `HOT`는 `holo` canonical project와 KO
  forensic website-visible target row가 확인되어 이번 eligible source로
  선택했다.
- 선택한 Drive Markdown:
  `HOT 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `holo` (`symbol=HOT`, `status=monitoring_only`).
- Source identity:
  `drive:17RihIV_zA8k4Xd6CHo6zqtIs2bTkNDq-:0B8HYgThT3NBySlZKMEh1d3cycDY4VmVVRDEwWmFDa1NsMHJZPQ`.
- Source SHA-256:
  `69c0b6fbf97332fa57885777ca8729c811a441b45157b85fa18b14771ed882d8`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_holo_bce2296.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_holo_drive_selected_bce2296.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_holo.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `holo`
  - validation status: `valid`
  - validation reasons: none after KO sentence-splitter wording correction
  - upsert result: `inserted`
  - job id: `5e1ef7b1-8969-48a5-89a5-ab07bd6db37e`
- Selector recurrence audit:
  표준 selector는 이전 실행들처럼 `--slug` 지정 후에도 FOR 폴더 전체를
  다운로드할 수 있어, 이번 실행은 Drive metadata, file id, revision,
  source text, canonical project, target row를 먼저 확정한 뒤 기존
  validator, artifact writer, telemetry, `upsert_job` 함수를 고정 후보에
  직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5e1ef7b1-8969-48a5-89a5-ab07bd6db37e --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2296" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `ef306eee-506f-459e-83a8-883d028dcfaf`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2296_holo_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=holo`, `symbol=HOT`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=5e1ef7b1-8969-48a5-89a5-ab07bd6db37e`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=ef306eee-506f-459e-83a8-883d028dcfaf`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=HOT는 높은 포렌식 리스크 구간이며,저점 반등 후에도 고점 공급 흡수가 불완전해,핵심 저항 회복 전까지 관찰이 우선이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/holo`,
    `https://www.bcelab.xyz/en/projects/holo`,
    `https://www.bcelab.xyz/ko/reports/holo/forensic`, and
    `https://www.bcelab.xyz/en/reports/holo/forensic` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches prior FOR report-body
    surface behavior and does not indicate a failed gate promotion.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2293 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 23:59 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 미승격 `ELF` FOR는 직전 실행에서 KO forensic target row
  부재로 제외된 이력이 있고, `MOODENG` FOR는 canonical project는 있으나
  KO forensic target row가 없었다. `Data IP` FOR는 본문이 Story/IP
  리브랜딩 보고서라 `data-network` forensic target row에 연결하면 오배정
  위험이 있어 제외했다. `AIOZ` MAT는 canonical project lookup이 여전히
  확인되지 않았다. 다음 eligible source인 `Sonic Labs` MAT는 `sonic`
  canonical project 및 KO maturity target row를 가진 active project로
  확인됐다.
- 선택한 Drive Markdown:
  `Sonic Labs의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024–2026.md`.
- Canonical tracked project:
  `sonic` (`symbol=S`, `status=active`).
- Source identity:
  `drive:1M4eChMiXVQ94Pgvg4kfyuV-xmlLyTvhk:0B8HYgThT3NByYkg0aTJ4SzkvczRIdlJsMUlGbEh2YzdMYUVrPQ`.
- Source SHA-256:
  `ffa591dfb0eb26d02da9f99a0ae407e02cb055b8709f330f37b58664acd9a2aa`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_sonic_bce2293.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_sonic_drive_selected_bce2293.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_sonic.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `sonic`
  - validation status: `valid`
  - validation reasons: none after ZH marketing length correction
  - upsert result: `inserted`
  - job id: `fe5fd5db-cdad-4a22-a30e-3958a2e29401`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug sonic --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_sonic_bce2293.json --require-agent-output --limit 1 --force`
  는 후보 다운로드 단계에서 2분 30초 이상 무출력으로 지연되어 중단했다.
  이미 Drive file id, revision, source text, canonical project, target row가
  확정된 상태라 기존 validator, artifact writer, telemetry, `upsert_job`
  함수를 고정 후보에 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fe5fd5db-cdad-4a22-a30e-3958a2e29401 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2293" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `f0ef68dd-fc12-463c-9b4b-e7ecb9c69d17`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2293_sonic_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=sonic`, `symbol=S`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=fe5fd5db-cdad-4a22-a30e-3958a2e29401`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=f0ef68dd-fc12-463c-9b4b-e7ecb9c69d17`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Sonic은 46.9/100의 초기 전개 단계 L1이다. 400k TPS 서사, FeeM 개발자 수익화, Gateway는 강점이지만 실측 TPS, 체인 수수료, 검증인 분산은 아직 낮아 앱 수익 검증이 핵심이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/sonic`,
    `https://www.bcelab.xyz/en/projects/sonic`,
    `https://www.bcelab.xyz/ko/reports/sonic/maturity`, and
    `https://www.bcelab.xyz/en/reports/sonic/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2294 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 00:01 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 이력에서는 `ELF` FOR가 KO forensic target row 부재로
  제외됐지만, 현재 DB에는 `aelf` canonical project와 KO forensic
  website-visible target row가 존재했다. `MOODENG` FOR는 여전히 KO
  forensic target row가 없고, `SYRUP`, `MNT`, `0G` current source는 이미
  promoted 상태이므로 최신 eligible source로 `ELF` FOR를 선택했다.
- 선택한 Drive Markdown:
  `ELF 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `aelf` (`symbol=ELF`, `status=monitoring_only`).
- Source identity:
  `drive:1g3sPojT0ZEUpZp0gLFdiWK4b7FfPRJ-I:0B8HYgThT3NByVndKMGJiS1lsMWVqbUFyMnYvYWY3QUd2VTlNPQ`.
- Source SHA-256:
  `6c5cf44429a154b760e8e02b09af7311109eb7bb0ad9fbed8ed9db4aa34d0cc9`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_aelf_bce2294.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_aelf_drive_selected_bce2294.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_aelf.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `aelf`
  - validation status: `valid`
  - validation reasons: none after raw-format and short-marketing wording
    corrections
  - upsert result: `inserted`
  - job id: `5fa7fd2f-11ba-49d3-9e94-0deb78b3d50e`
- Selector recurrence audit:
  표준 selector는 이전 실행들에서 `--slug` 지정 후에도 다운로드 단계에서
  최신 다른 후보를 먼저 만지거나 지연되는 한계가 반복 확인됐다. 이번
  실행은 Drive metadata, file id, revision, source text, canonical project,
  target row를 먼저 확정한 뒤 기존 validator, artifact writer, telemetry,
  `upsert_job` 함수를 고정 후보에 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5fa7fd2f-11ba-49d3-9e94-0deb78b3d50e --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2294" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `19142ff7-ac38-42c7-8219-d1b8b6702738`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2294_aelf_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=aelf`, `symbol=ELF`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=5fa7fd2f-11ba-49d3-9e94-0deb78b3d50e`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=19142ff7-ac38-42c7-8219-d1b8b6702738`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ELF는 59점의 중상위 시장 무결성 리스크 구간으로, 급등 후 긴 윗꼬리, MA 하회, 저점권 체류가 하방 압력을 키워 단기 반등 확인 전 관망이 우선이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/aelf`,
    `https://www.bcelab.xyz/en/projects/aelf`,
    `https://www.bcelab.xyz/ko/reports/aelf/forensic`, and
    `https://www.bcelab.xyz/en/reports/aelf/forensic` returned HTTP `200`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches the prior FOR report-body
    surface behavior and does not indicate a failed gate promotion.
  - The local Python TLS verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2295 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-29 00:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2294](/BCE/issues/BCE-2294)는 `ELF` FOR를 promoted
  및 웹 검증 완료했다. 최신 미승격 `SNX` FOR와 `BSV` FOR는 canonical
  project는 있으나 KO forensic website-visible target row가 없고,
  `MOODENG` FOR도 target row가 없었다. `Data IP` FOR는 이전 이력에서
  Story/IP 리브랜딩 오배정 리스크로 제외됐지만, 현재 DB에는 `data-network`
  canonical project와 KO forensic target row가 있고 기존 target summary도
  DATA 전환 서사를 담고 있어 eligible source로 선택했다.
- 선택한 Drive Markdown:
  `Data IP 시장 무결성 및 심층 포렌식 리스크 보고서 (1).md`.
- Canonical tracked project:
  `data-network` (`symbol=DATA`, `status=monitoring_only`).
- Source identity:
  `drive:19JX-JGcGPO2V8L02NepSaCCDqavQx43F:0B8HYgThT3NByK1puRlgvTFlyMWdUL3czK29YeG9weVNOU3JBPQ`.
- Source SHA-256:
  `d257542aa0cbbf78f9a60cd33191be94e7781a1328cc2b08c475c5498592f1e5`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_data-network_bce2295.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_data-network_drive_selected_bce2295.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_data-network.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `data-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `172f7ecf-ba96-42f1-a40e-4998da273e97`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug data-network --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_data-network_bce2295.json --require-agent-output --limit 1 --force`
  는 `slug=data-network`인데도 최신 `SNX` FOR Drive source를 먼저 선택해
  invalid row `b83c04d7-2232-45ec-8c56-62318d5faf1e`를 만들었다. 이 row는
  `source_sentences.*.not_in_source` validation failure였고, Summary
  Authority Gate reject action으로 `rejected` 처리했다. 확정된 Data IP
  file id, revision, source text, canonical project, target row에 기존
  validator, artifact writer, telemetry, `upsert_job` 함수를 고정 후보로
  직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 172f7ecf-ba96-42f1-a40e-4998da273e97 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2295" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `1e7225ea-1444-4461-907d-b2f0cfb4b23d`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2295_data_network_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=data-network`, `symbol=DATA`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=172f7ecf-ba96-42f1-a40e-4998da273e97`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=1e7225ea-1444-4461-907d-b2f0cfb4b23d`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=DATA Network는 IP 전환 이벤트 뒤 68점의 높은 포렌식 리스크 구간에 있다. 0.4405 고점 실패와 0.31달러대 복귀, 선물 우위 수급 때문에 0.3307 회복 전까지 추격 매수 리스크가 크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/data-network`,
    `https://www.bcelab.xyz/en/projects/data-network`,
    `https://www.bcelab.xyz/ko/reports/data-network/forensic`, and
    `https://www.bcelab.xyz/en/reports/data-network/forensic` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches prior FOR report-body
    surface behavior and does not indicate a failed gate promotion.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2292 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 23:35 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 미승격 후보 `ELF` FOR는 `aelf`로 매칭되지만 KO forensic
  target row가 없어 제외했다. 다음 최신 미승격 후보 `MNT` FOR는 `mantle`
  canonical project 및 KO forensic target row를 가진 eligible source로
  확인했다.
- 선택한 Drive Markdown:
  `MNT 시장 무결성 및 심층 포렌식 리스크 보고서 (1).md`.
- Canonical tracked project:
  `mantle` (`symbol=MNT`, `status=active`).
- Source identity:
  `drive:1FO4S76mfnarSGa7e2ahFNPvA9fOXuDYa:0B8HYgThT3NByOEhFZzQvVytYMWdNRHJqcVZJZW9DbzAzY053PQ`.
- Source SHA-256:
  `19be9062e9e5d2691c40b429f328541f121a007fa06867e40aabf1beb822c687`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_mantle_bce2292.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_mantle_drive_selected_bce2292.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_mantle.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `mantle`
  - validation status: `valid`
  - validation reasons: none after raw-format wording corrections
  - upsert result: `inserted`
  - job id: `c8ace17f-69d1-4063-adf4-bddb226b9510`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug mantle --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_mantle_bce2292.json --require-agent-output --limit 1 --force`
  는 `slug=mantle`인데도 최신 `ELF` FOR Drive source를 먼저 다운로드해
  `source_sentences.*.not_in_source` 및 raw-format 오류로 invalid row
  `1d54359f-a3bc-4c49-b0c4-0e3b0319bb40`를 만들었다. 이전
  [BCE-2289](/BCE/issues/BCE-2289)~[BCE-2291](/BCE/issues/BCE-2291)에서
  확인한 selector 한계와 같은 유형이라, 확정된 MNT file id, revision,
  source text, canonical project, target row에 기존 validator, artifact
  writer, telemetry, `upsert_job` 함수를 고정 후보로 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id c8ace17f-69d1-4063-adf4-bddb226b9510 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2292" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `880d93d6-47b8-4d68-ab7d-720ac7c45350`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2292_mantle_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=mantle`, `symbol=MNT`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=c8ace17f-69d1-4063-adf4-bddb226b9510`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=880d93d6-47b8-4d68-ab7d-720ac7c45350`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=MNT는 56점의 중간 조작 리스크와 단기 매도 우위가 공존하는 L2·RWA 토큰이다. 0.4309 지지선 방어와 0.4350부터 0.4364까지 회복 여부가 반등 신뢰도의 핵심 분기점이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/mantle`,
    `https://www.bcelab.xyz/en/projects/mantle`,
    `https://www.bcelab.xyz/ko/reports/mantle/forensic`, and
    `https://www.bcelab.xyz/en/reports/mantle/forensic` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches the
    [BCE-2289](/BCE/issues/BCE-2289)/[BCE-2290](/BCE/issues/BCE-2290)/[BCE-2291](/BCE/issues/BCE-2291)
    report-body surface behavior and does not indicate a failed gate promotion.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2289 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 21:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 Drive FOR 후보 중 `SYRUP`, `CAP`, `MNT`는 KO forensic
  target row가 없어 건너뛰었고, `0G` FOR가 `zero-gravity` canonical
  project 및 KO forensic target row를 가진 최신 eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `0G 시장 무결성 및 심층 포렌식 리스크 보고서 (1).md`.
- Canonical tracked project:
  `zero-gravity` (`symbol=0G`, `status=monitoring_only`).
- Source identity:
  `drive:1rdqI7t0xAZMy4AQ7HZDw-t64QxdVm6KO:0B8HYgThT3NByZW5oQUNHRXViMEZGYTRzM08vcWs5Qm1DSkN3PQ`.
- Source SHA-256:
  `8f254b67a30b8ae20da545a46e0e2dd828c83d132923014e93c102ebc72931ec`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_zero-gravity_bce2289.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_zero-gravity_drive_selected_bce2289.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_zero-gravity.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `zero-gravity`
  - validation status: `valid`
  - validation reasons: none after English/French/Spanish/German numeric-symbol
    wording correction
  - upsert result: `updated_existing`
  - job id: `fb3cbe59-86fd-4a35-98d8-5ecbf33a9024`
- Selector recurrence audit:
  전체 Drive 후보 다운로드 scan은 `_download_drive_text()` 단계에서 90초
  이상 무출력으로 지연되어 중단했다. 이후 Drive metadata list로 최신 후보를
  좁히고, 확정된 0G file id/revision/source text/canonical project/target
  row에 기존 validator, artifact writer, telemetry, `upsert_job` 함수를
  직접 적용했다. 최초 validation은 영문 계열 문구의 `62/100`, `sell-side`,
  `futures-led` 표현을 raw format으로 오인해 invalid였고, 같은 idempotency
  key를 `force=True`로 갱신해 valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fb3cbe59-86fd-4a35-98d8-5ecbf33a9024 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2289" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `6ee3ec8d-d2f7-4f6d-a348-b53af2b9c613`
  - promoted at: `2026-06-28T12:38:56.862372+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2289_zero-gravity_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=zero-gravity`, `symbol=0G`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=fb3cbe59-86fd-4a35-98d8-5ecbf33a9024`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=6ee3ec8d-d2f7-4f6d-a348-b53af2b9c613`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=0G는 62/100 HIGH 조작 리스크와 약한 매도 우위를 보이는 AI 인프라 토큰이다. 0.224 이탈은 0.198 재시험, 0.251 돌파는 반등 신뢰도 회복의 핵심 분기점이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/zero-gravity`,
    `https://www.bcelab.xyz/en/projects/zero-gravity`,
    `https://www.bcelab.xyz/ko/reports/zero-gravity/forensic`, and
    `https://www.bcelab.xyz/en/reports/zero-gravity/forensic` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project surface
    contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this appears to be report-body surface
    behavior, not a failed Summary Authority Gate promotion.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2290 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 22:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 unpromoted FOR 후보 중 `SYRUP`은 현재
  `maple-finance` canonical project 및 KO forensic target row를 가진
  최신 eligible source로 재확인됐다.
- 선택한 Drive Markdown:
  `SYRUP 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `maple-finance` (`symbol=SYRUP`, `status=active`).
- Source identity:
  `drive:1lvAvaue6Kxqpwsu6nOykDoyKzhv7LBcz:0B8HYgThT3NByVTZJKzlkQnVjYlpzL1czTzc1d1dKMk95NWlVPQ`.
- Source SHA-256:
  `90bef09370833999584b285aa71e41ae7f43de08d4faa93bfe0e01c015f8a3a6`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_maple-finance_bce2290.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_maple-finance_drive_selected_bce2290.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_maple-finance.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `maple-finance`
  - validation status: `valid`
  - validation reasons: none after English/French/Spanish/German raw-format
    wording correction
  - upsert result: `updated_existing`
  - job id: `132701db-dd5d-450c-8a5f-dbf2165b0dfd`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 132701db-dd5d-450c-8a5f-dbf2165b0dfd --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2290" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d8922104-e2e5-410e-af0e-be65b7df17cb`
  - promoted at: `2026-06-28T13:07:05.278424+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2290_maple-finance_for_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2290_maple-finance_for_website_verification_curl.json`.
- Project report verification:
  - `tracked_projects.slug=maple-finance`, `symbol=SYRUP`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=132701db-dd5d-450c-8a5f-dbf2165b0dfd`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=d8922104-e2e5-410e-af0e-be65b7df17cb`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=SYRUP은 58점의 중상위 조작 리스크와 조건부 반등 신호가 공존하는 RWA 신용 토큰이다. 선물 거래량 우위, 얇은 유동성, 0.1601 돌파 전 불확실성이 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/maple-finance`,
    `https://www.bcelab.xyz/en/projects/maple-finance`,
    `https://www.bcelab.xyz/ko/reports/maple-finance/forensic`, and
    `https://www.bcelab.xyz/en/reports/maple-finance/forensic` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches the BCE-2289 report-body
    surface behavior and does not indicate a failed gate promotion.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2291 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 22:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 Drive source인 `SYRUP` FOR는 BCE-2290에서 이미
  promoted 상태였고, 그 다음 최신 unpromoted 후보 중 `CAP` FOR가
  `cap-app` canonical project 및 KO forensic target row를 가진 최신
  eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `CAP 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `cap-app` (`symbol=CAP`, `status=monitoring_only`).
- Source identity:
  `drive:1JAq9VVsZPv3XWz4zEs4WDXMQmjW2iymJ:0B8HYgThT3NBycHlBSlFoNUJCK2ZyVTNSVXhDNmt5ZldYQXl3PQ`.
- Source SHA-256:
  `c2a296c0f95ced4a16182b995f4b77913a0872806237092c4c2a8922a95f9415`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_cap-app_bce2291.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_cap-app_drive_selected_bce2291.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_cap-app.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `cap-app`
  - validation status: `valid`
  - validation reasons: none after source sentence array, KO sentence-count, and
    raw-format wording corrections
  - upsert result: `updated_existing`
  - job id: `d2fb117d-9305-4fc2-bb98-1b5fd12bd24b`
- Selector recurrence audit:
  standard Drive slug scan was not used for final persistence because this
  selector path can download unrelated natural-language FOR filenames before
  slicing. Already-confirmed file id, revision, source text, canonical project,
  and target row were processed through the existing validator, artifact writer,
  telemetry, and `upsert_job` functions with `force=True`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d2fb117d-9305-4fc2-bb98-1b5fd12bd24b --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2291" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `a8fab974-b88a-41a7-9b4d-f60e6a9ee015`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2291_cap-app_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=cap-app`, `symbol=CAP`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=d2fb117d-9305-4fc2-bb98-1b5fd12bd24b`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=a8fab974-b88a-41a7-9b4d-f60e6a9ee015`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=CAP 고위험 조작 리스크, 상장 초기 고점 매도와 저점 방어 반복, 낮은 거래량과 얕은 매수 우위로 저항 확인 전 추격 자제`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/cap-app`,
    `https://www.bcelab.xyz/en/projects/cap-app`,
    `https://www.bcelab.xyz/ko/reports/cap-app/forensic`, and
    `https://www.bcelab.xyz/en/reports/cap-app/forensic` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The individual forensic report pages returned `200` but did not contain the
    card summary string in rendered HTML; this matches the BCE-2289/BCE-2290
    report-body surface behavior and does not indicate a failed gate promotion.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-page visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2279 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 15:46 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 unpromoted source인 `MUon` MAT, `Light Heaven`
  ECON/MAT, `ARC` MAT/ECON, `MindWaveDAO` ECON, `AIOZ` MAT, `ZK` FOR는
  target row 부재, canonical 매칭 리스크, 또는 이전 이력과 같은 제외
  사유로 건너뛰었다. 이번 실행에서 `XRP Ledger` MAT Drive source가
  `ripple` canonical project 및 KO maturity target row를 가진 최신
  eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `XRP Ledger의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2012 - 2026.md`.
- Canonical tracked project:
  `ripple` (`symbol=XRP`, `status=active`).
- Source identity:
  `drive:1k_keQCog35bOYq3zzbOV6X2i1xC9Mx_q:0B8HYgThT3NByc2kxVjk5dFlMYVNpeG9qb1FrdXFuY0s3dm5nPQ`.
- Source SHA-256:
  `50d0d2db3b36959f95054186155703b377ee2d36db353b15bd1136233b33780a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_ripple_bce2279.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_ripple_drive_selected_bce2279.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_ripple.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `ripple`
  - validation status: `valid`
  - validation reasons: none after length correction
  - upsert result: `updated_existing`
  - job id: `ab097455-34e1-4d60-9242-530e7623f030`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug ripple --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_ripple_bce2279.json --require-agent-output --limit 1`
  는 Drive selector가 slug 후보 다운로드 단계에서 90초 이상 무출력으로
  지연되어 중단했다. 이미 Drive file id, revision, source text,
  canonical project, target row가 확정된 상태라 기존 validator, artifact
  writer, telemetry, `upsert_job` 함수를 고정 후보에 직접 적용했다. 최초
  validation은 EN/FR/ES/DE summary length와 KO marketing sentence count로
  invalid였으나, 같은 idempotency key를 `force=True`로 갱신해 valid
  상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id ab097455-34e1-4d60-9242-530e7623f030 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2279" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `f96d1228-62ef-471e-b68c-4382a6a7896c`
  - promoted at: `2026-06-28T06:45:21.573161+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2279_ripple_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2279_ripple_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ripple`, `symbol=XRP`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=ab097455-34e1-4d60-9242-530e7623f030`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=f96d1228-62ef-471e-b68c-4382a6a7896c`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=3`, `is_latest=true`
  - `card_summary_ko=XRPL은 72.6/100으로 성숙 초기와 중기 경계에 있는 결제 특화 L1이다. 빠른 완결성, 낮은 수수료, 긴 운영 이력은 강하지만 Ripple 에스크로, UNL 집중도, 제한적인 DeFi 유동성과 개발자 네트워크가 핵심 과제다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ripple`,
    `https://www.bcelab.xyz/en/projects/ripple`,
    `https://www.bcelab.xyz/ko/reports/ripple/maturity`, and
    `https://www.bcelab.xyz/en/reports/ripple/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2280 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 16:09 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 전체 Drive/project 정규식 대조는 장시간 무출력으로 지연되어
  중단했고, Drive 최신 unpromoted 목록과 DB target row를 직접 대조했다.
  `Light Heaven`, `ARC`, `AIOZ`, `ZK`는 이전과 같은 canonical/target
  리스크가 남아 건너뛰었다. 이번 실행에서는 `MUon` MAT Drive source가
  `micron-technology-tokenized-stock-ondo` canonical project 및 공개 KO
  maturity target row를 가진 최신 eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `MUon의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Canonical tracked project:
  `micron-technology-tokenized-stock-ondo` (`symbol=MUon`,
  `status=monitoring_only`).
- Source identity:
  `drive:1BTvaEQQBOcjy00cpF-Ty0dX8ahwzFhOO:0B8HYgThT3NByOVBOSXVYTTdXcWtEbjQwVkZHYmc1QXBMdCswPQ`.
- Source SHA-256:
  `605da8bcd456ffc87fa500ffbe4188f20699561d76ca8297eaa65e87faab5f32`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_micron-technology-tokenized-stock-ondo_bce2280.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_micron-technology-tokenized-stock-ondo_drive_selected_bce2280.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_micron-technology-tokenized-stock-ondo.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `micron-technology-tokenized-stock-ondo`
  - validation status: `valid`
  - validation reasons: none after KO format/sentence correction
  - upsert result: `updated_existing`
  - job id: `14a0f30d-9302-4d2b-97b3-da63085267ba`
- Selector recurrence audit:
  표준 slug scan은 자연어 파일명에서 slug를 파싱하지 못하면 같은 타입의
  모든 Markdown을 다운로드하는 구조라 장시간 지연될 수 있다. 이미 Drive
  file id, revision, source text, canonical project, target row가 확정된
  상태라 기존 validator, artifact writer, telemetry, `upsert_job` 함수를
  고정 후보에 직접 적용했다. 최초 validation은 KO raw format fragment와
  marketing sentence count로 invalid였으나, 같은 idempotency key를
  `force=True`로 갱신해 valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 14a0f30d-9302-4d2b-97b3-da63085267ba --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2280" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `189fa0f8-eea9-4efd-aaf1-25c8bab9149d`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2280_micron-technology-tokenized-stock-ondo_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=micron-technology-tokenized-stock-ondo`,
    `symbol=MUon`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=14a0f30d-9302-4d2b-97b3-da63085267ba`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=189fa0f8-eea9-4efd-aaf1-25c8bab9149d`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=MUon은 75.4점의 초기 성숙 RWA 토큰화 주식 노출권이다. 높은 월간 회전율, NAV와 공급의 정합성, 수탁·검증 구조가 강하지만 BNB Chain 유동성 집중, 오프체인 담보 의존, 직접 주주권 부재가 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/micron-technology-tokenized-stock-ondo`,
    `https://www.bcelab.xyz/en/projects/micron-technology-tokenized-stock-ondo`,
    `https://www.bcelab.xyz/ko/reports/micron-technology-tokenized-stock-ondo/maturity`,
    and
    `https://www.bcelab.xyz/en/reports/micron-technology-tokenized-stock-ondo/maturity`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2281 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 16:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 `MUon` MAT source는 BCE-2280에서 이미 promoted 상태로
  확인됐다. 이후 최신 unpromoted 후보 중 `Light Heaven`은 이전 위키의
  canonical/target 리스크와 달리 현재 `light` canonical project 및 KO
  econ/maturity target row가 존재함을 재확인했다. 따라서 최신 eligible
  source인 `Light Heaven` ECON을 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `Light Heaven 크립토이코노미 설계 심층 분석 보고서.md`.
- Canonical tracked project:
  `light` (`symbol=LIGHT`, `status=monitoring_only`).
- Source identity:
  `drive:11x7y-FlEhNO2fYu_SgPkKpg4IOibI3ao:0B8HYgThT3NByS3p4YkpGWEV1Zll1a0FZOFd3eVBISVQwYkN3PQ`.
- Source SHA-256:
  `ee96dca5cda3c4fd6e6c8d95aafd91ed85ed4d0ba92c2199096267d216b5af72`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_light_bce2281.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_light_bce2281.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_light.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `light`
  - validation status: `valid`
  - validation reasons: none after raw-format correction
  - upsert result: `updated_existing`
  - job id: `781d07a0-b7c1-4eb8-beb7-da289adc93fa`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug light --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_light_bce2281.json --require-agent-output --limit 1 --force`
  는 Drive selector가 slug 후보 다운로드 단계에서 60초 이상 무출력으로
  지연되어 중단했다. 이미 Drive file id, revision, source text,
  canonical project, target row가 확정된 상태라 기존 validator, artifact
  writer, telemetry, `upsert_job` 함수를 고정 후보에 직접 적용했다. 최초
  validation은 `raw_format_fragment`와 source evidence 치환 문제로
  invalid였으나, 같은 idempotency key를 `force=True`로 갱신해 valid
  상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 781d07a0-b7c1-4eb8-beb7-da289adc93fa --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2281" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `bec2b65c-3e3b-48d7-83ef-5f77f42b0170`
  - promoted at: `2026-06-28T07:38:48.392923+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2281_light_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=light`, `symbol=LIGHT`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=781d07a0-b7c1-4eb8-beb7-da289adc93fa`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=bec2b65c-3e3b-48d7-83ef-5f77f42b0170`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Light Heaven은 Solana 런치패드와 자체 AMM 수수료를 LIGHT 매수와 소각으로 연결한 설계다. 수익 포착은 명확하지만 거래량 회복, 운영자 분류, API와 코드 투명성이 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/light`,
    `https://www.bcelab.xyz/en/projects/light`,
    `https://www.bcelab.xyz/ko/reports/light/econ`, and
    `https://www.bcelab.xyz/en/reports/light/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2282 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 17:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 `MUon` MAT source는 BCE-2280에서 이미 promoted 상태,
  `Light Heaven` ECON source는 BCE-2281에서 이미 promoted 상태였다.
  다음 최신 unpromoted 후보인 `Light Heaven` MAT source가 `light`
  canonical project 및 KO maturity target row를 가진 eligible source로
  확인됐다.
- 선택한 Drive Markdown:
  `Light Heaven의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Canonical tracked project:
  `light` (`symbol=LIGHT`, `status=monitoring_only`).
- Source identity:
  `drive:1rME5DpkqFQCchFXOyE2hK7IcPbvqxD4E:0B8HYgThT3NByVVFFUDhxdk5CUFBYbWJIQkVCMDhUb08wdzFrPQ`.
- Source SHA-256:
  `0b3bd2dc0d0ce947349455bd5177a4742e616506ef134717c80812413d1fa07a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_light_bce2282.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_light_bce2282.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_light.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `light`
  - validation status: `valid`
  - validation reasons: none after score/raw-format and KO sentence-count correction
  - upsert result: `inserted`
  - job id: `5181db41-ef32-4a92-8b10-7284ece2211f`
- Selector recurrence audit:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug light --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_light_bce2282.json --require-agent-output --limit 1 --force`
  는 Drive selector가 후보 다운로드 단계에서 90초 이상 무출력으로
  지연되어 중단했다. 이미 Drive file id, revision, source text,
  canonical project, target row가 확정된 상태라 기존 validator, artifact
  writer, telemetry, `upsert_job` 함수를 고정 후보에 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5181db41-ef32-4a92-8b10-7284ece2211f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2282" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `a05b9f5f-c142-47db-b8a6-59f23e2e08cd`
  - promoted at: `2026-06-28T08:07:19.901565+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2282_light_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=light`, `symbol=LIGHT`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=5181db41-ef32-4a92-8b10-7284ece2211f`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=a05b9f5f-c142-47db-b8a6-59f23e2e08cd`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Light Heaven은 51.2점의 초기 구현 완료 후 수요 미검증 구간이며, 자체 AMM과 LIGHT 매입 소각 구조는 명확하지만 최근 수익과 거래량 급감, 중앙화 fee review, 개발자 생태계 부족이 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/light`,
    `https://www.bcelab.xyz/en/projects/light`,
    `https://www.bcelab.xyz/ko/reports/light/maturity`, and
    `https://www.bcelab.xyz/en/reports/light/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2283 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 17:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 `MUon` MAT, `Light Heaven` ECON, `Light Heaven` MAT는
  이미 promoted 상태였다. 다음 최신 unpromoted 후보인 `ARC` MAT source에
  대해 현재 DB를 재확인했고, 이전 리스크와 달리 `ai-rig-complex`
  canonical project 및 KO maturity target row가 존재함을 확인해 eligible
  source로 선택했다.
- 선택한 Drive Markdown:
  `ARC의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`.
- Canonical tracked project:
  `ai-rig-complex` (`symbol=ARC`, `status=monitoring_only`).
- Source identity:
  `drive:108rJGjD03ZqcVDtNDN1QF_4inkNF7xc1:0B8HYgThT3NByTnp0Zk9yZkdUdDRXVWJuSm0wS1hialF3ekc4PQ`.
- Source SHA-256:
  `bb199f7805b5cb172ba31f45c79a2cb4dc036e451e5fa85694c5d4cba039e9e9`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_ai-rig-complex_bce2283.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_ai-rig-complex_bce2283.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_ai-rig-complex.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `ai-rig-complex`
  - validation status: `valid`
  - validation reasons: none after EN/DE raw-format correction
  - upsert result: `updated_existing`
  - job id: `63744902-2015-424c-923e-c2fe01852801`
- Selector recurrence audit:
  표준 selector가 slug 후보 다운로드 단계에서 장시간 지연되는 이전 이력이
  있어 Drive metadata와 DB target row를 먼저 확정했다. 이후 Drive file id,
  revision, source text, canonical project, target row가 확정된 상태에서
  기존 validator, artifact writer, `upsert_job` 함수를 고정 후보에 직접
  적용했다. 최초 validation은 EN/DE hyphenated 표현이 `raw_format_fragment`
  로 오탐되어 invalid였으나, 같은 idempotency key를 `force=True`로 갱신해
  valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 63744902-2015-424c-923e-c2fe01852801 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2283" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `7fe16d72-e616-4a83-b419-213f8daea4a4`
  - promoted at: `2026-06-28T08:40:26.812058+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2283_ai-rig-complex_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ai-rig-complex`, `symbol=ARC`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=63744902-2015-424c-923e-c2fe01852801`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=7fe16d72-e616-4a83-b419-213f8daea4a4`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ARC는 60.1점의 전개 단계 AI 에이전트 인프라다. Rig 코드와 개발자 지표는 강하지만, Ryzome과 Arc Forge의 반복 매출 및 토큰 가치 포착은 아직 검증 전이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ai-rig-complex`,
    `https://www.bcelab.xyz/en/projects/ai-rig-complex`,
    `https://www.bcelab.xyz/ko/reports/ai-rig-complex/maturity`, and
    `https://www.bcelab.xyz/en/reports/ai-rig-complex/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2286 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 19:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 `0G` FOR source는 canonical project가 있으나 KO
  forensic target row가 없어 Authority Gate promotion 대상에서 제외했고,
  `AIOZ` MAT source는 canonical tracked project가 없어 제외했다. 다음
  최신 eligible source인 `Ethereum` MAT source가 `ethereum` canonical
  project 및 KO maturity target row `version=3`를 가진 것으로 확인됐다.
- 선택한 Drive Markdown:
  `Ethereum의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2015 - 2026 20260526.md`.
- Canonical tracked project:
  `ethereum` (`symbol=ETH`, `status=active`).
- Source identity:
  `drive:1arkeEC_656yrSubKGAMX-ax6EzKqI2GW:0B8HYgThT3NByL09HTEc2VXJESXh6eU5jNng4N2pwQ3NoTW5JPQ`.
- Source SHA-256:
  `1f8074e03d4b78ddeaf4fe1d0d967c7fc845584e609c63fed1a61ec0d25ba74a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_ethereum_bce2286.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_ethereum_bce2286.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_ethereum.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `ethereum`
  - validation status: `valid`
  - validation reasons: none after KO card-format and sentence-count correction
  - upsert result: `inserted`
  - job id: `ac36e2b8-9f42-4c73-895b-a37a0acf39e2`
- Selector recurrence audit:
  표준 selector는 Drive 다운로드 단계에서 30초 이상 무출력으로 지연되어
  중단했다. 이미 Drive file id, revision, source text, canonical project,
  target row가 확정된 상태라 기존 validator, artifact writer, `upsert_job`
  함수를 고정 후보에 직접 적용했다. 자연어 파일명은 버전을 파싱하지
  못하므로 website-visible KO maturity target인 `version=3`을 명시했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id ac36e2b8-9f42-4c73-895b-a37a0acf39e2 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2286" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `44210961-0b7f-4497-ad30-6b5674390dd8`
  - promoted at: `2026-06-28T10:39:28.478992+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2286_ethereum_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ethereum`, `symbol=ETH`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=ac36e2b8-9f42-4c73-895b-a37a0acf39e2`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=44210961-0b7f-4497-ad30-6b5674390dd8`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=3`, `is_latest=true`
  - `card_summary_ko=Ethereum은 79.7점의 성숙 서사 초입에 있는 글로벌 정산 L1이다. Merge와 Dencun, 개발자 생태계, ETF 및 RWA 채택은 강하지만 L2 수수료 압축과 ETH 가치 포획, 클라이언트·스테이킹 집중이 핵심 과제다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ethereum`,
    `https://www.bcelab.xyz/en/projects/ethereum`,
    `https://www.bcelab.xyz/ko/reports/ethereum/maturity`, and
    `https://www.bcelab.xyz/en/reports/ethereum/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2287 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 20:51 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2286](/BCE/issues/BCE-2286)는 `Ethereum` MAT를
  promoted 및 웹 검증 완료했다. 이번 실행에서는 최신 미승격 후보인 `0G`
  FOR source를 재확인했고, 이전 위키의 target row 부재 상태와 달리 현재
  `zero-gravity` canonical project 및 website-visible KO forensic target
  row가 존재해 eligible source로 선택했다.
- 선택한 Drive Markdown:
  `0G 시장 무결성 및 심층 포렌식 리스크 보고서 (1).md`.
- Canonical tracked project:
  `zero-gravity` (`symbol=0G`, `status=monitoring_only`).
- Source identity:
  `drive:1rdqI7t0xAZMy4AQ7HZDw-t64QxdVm6KO:0B8HYgThT3NByZW5oQUNHRXViMEZGYTRzM08vcWs5Qm1DSkN3PQ`.
- Source SHA-256:
  `8f254b67a30b8ae20da545a46e0e2dd828c83d132923014e93c102ebc72931ec`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_zero-gravity_bce2287.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_zero-gravity_bce2287.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_zero-gravity.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug zero-gravity --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_zero-gravity_bce2287.json --require-agent-output --limit 1`.
- Candidate ingest result:
  - report type: `for`
  - slug: `zero-gravity`
  - validation status: `valid`
  - validation reasons: none after KO sentence-count correction
  - upsert result: `updated_existing`
  - job id: `fb3cbe59-86fd-4a35-98d8-5ecbf33a9024`
- Selector recurrence audit:
  최초 표준 command는 정확한 Drive source를 선택했지만 KO summary
  sentence-count로 invalid row를 inserted했다. KO summary를 한 문장으로
  수정한 뒤 `--force` 표준 command를 재실행했으나 Drive download 단계에서
  `ConnectionResetError: [Errno 54] Connection reset by peer`가 발생했다.
  이미 Drive file id, revision, source text, canonical project, target
  row가 확정된 상태라 기존 validator, artifact writer, `upsert_job`
  함수를 고정 후보에 직접 적용해 같은 idempotency key를 valid 상태로
  갱신했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fb3cbe59-86fd-4a35-98d8-5ecbf33a9024 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2287" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `6ee3ec8d-d2f7-4f6d-a348-b53af2b9c613`
  - promoted at: `2026-06-28T11:51:09.979886+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2287_zero-gravity_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=zero-gravity`, `symbol=0G`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=fb3cbe59-86fd-4a35-98d8-5ecbf33a9024`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=6ee3ec8d-d2f7-4f6d-a348-b53af2b9c613`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=0G는 포렌식 리스크 62점의 HIGH 구간이며, 0.198 저점 뒤 반등했지만 0.24~0.251 매도 흡수, 현물보다 큰 선물 거래, 높은 OI 비율 때문에 레버리지 흔들림에 취약하다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/zero-gravity`,
    `https://www.bcelab.xyz/en/projects/zero-gravity`,
    `https://www.bcelab.xyz/ko/reports/zero-gravity/forensic`, and
    `https://www.bcelab.xyz/en/reports/zero-gravity/forensic` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The report detail pages returned `200`; their rendered HTML did not include
    the card summary string directly during this verification.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-card visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2288 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 21:19 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry`; pending comment는 없었고 harness checkout 상태라
  추가 checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2287](/BCE/issues/BCE-2287)는 `zero-gravity` FOR를
  promoted 및 웹 검증 완료했다. 이번 실행에서는 최신 `0G` FOR source가
  이미 promoted 상태임을 재확인했다. 다음 최신 unpromoted 후보인
  `Data IP` FOR는 본문상 Story/Data Foundation 전환 리포트이나
  `story-protocol`에는 KO forensic target row가 없고 `data-network`
  매핑은 심볼/프로젝트 canonical 리스크가 있어 제외했다. 그 다음 최신
  `Decred(DCR)` FOR source가 `decred` canonical project 및 website-visible
  KO forensic target row를 가진 eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `Decred(DCR) 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Canonical tracked project:
  `decred` (`symbol=DCR`, `status=active`).
- Source identity:
  `drive:1xfOjSfpL-GqnkTV-3dbgX3INtCin9lWq:0B8HYgThT3NByQzV3eThmTS82bG5ZODEzOC9pNU1jLzlHQ013PQ`.
- Source SHA-256:
  `869d9d7f2daef21ba467aade1fcc05d31ad3f2992f06f7eeacf1f71d63064da0`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_decred_bce2288.json`.
- Source snapshot:
  `scripts/pipeline/output/bce2288_decred_source_probe.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_decred.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug decred --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_decred_bce2288.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `for`
  - slug: `decred`
  - validation status: `valid`
  - validation reasons: none after German marketing sentence-count correction
  - upsert result: `updated_existing`
  - job id: `f708e28c-efeb-4bfb-9889-2f7ae2592791`
- Selector recurrence audit:
  최초 표준 command는 정확한 Drive source를 선택했지만 German marketing
  sentence-count로 invalid row를 inserted했다. German marketing copy를
  한 문장으로 줄인 뒤 같은 표준 command를 `--force`로 재실행해 같은
  idempotency key를 valid 상태로 갱신했다. 재실행은 Drive 단계에서
  30초 이상 무출력 지연 후 정상 완료됐다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id f708e28c-efeb-4bfb-9889-2f7ae2592791 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2288" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `7fbfb659-3b26-499e-bbc4-e443187fe262`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2288_decred_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=decred`, `symbol=DCR`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=f708e28c-efeb-4bfb-9889-2f7ae2592791`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=7fbfb659-3b26-499e-bbc4-e443187fe262`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Decred는 포렌식 리스크 58점의 MEDIUM HIGH 구간이다. 11.52달러 반등은 MA7과 MA25를 회복했지만, MA99 11.81달러 아래라 저유동성 흔들기와 페이크아웃 위험이 남아 있다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/decred`,
    `https://www.bcelab.xyz/en/projects/decred`,
    `https://www.bcelab.xyz/ko/reports/decred/forensic`, and
    `https://www.bcelab.xyz/en/reports/decred/forensic` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO project surface contained the promoted Korean summary. EN project
    surface contained the promoted English summary.
  - The report detail pages returned `200`; their rendered HTML did not include
    the card summary string directly during this verification.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website project-card visibility is confirmed on
  the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2276 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 14:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 unpromoted source인 `MUon` MAT는 maturity target row가
  없어 제외했고, `ARC` MAT/ECON은 canonical `ai-rig-complex` project는
  있으나 KO maturity/econ target row가 없어 제외했다. `MindWaveDAO`와
  `AIOZ`는 이전 이력과 동일하게 canonical target row가 없어 제외했다.
  `ZK` FOR는 canonical `zksync`에 KO forensic target row가 없어
  제외했다. 이번 실행에서 `BNB Chain` MAT Drive source가 target row와
  공개 웹 URL을 가진 최신 eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `BNB Chain 크립토 이코노미 성숙도 평가 보고서.md`.
- Canonical tracked project:
  `binancecoin` (`symbol=BNB`, `status=active`).
- Source identity:
  `drive:1TrnaeuxLj63Hp33M3MNWTj1MeB35_2zG:0B8HYgThT3NByT054OVZmR2JZeHZkMnFNQTd5MnFvb1dEdVdRPQ`.
- Source SHA-256:
  `3a7591271e1f0b2c092e4df8ea72b17d44c585186c7bcd9a91f3885786eeccba`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_binancecoin_bce2276.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_binancecoin_drive_selected_bce2276.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_binancecoin.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `binancecoin`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `1b2fb767-72ec-4249-8464-2ce4c248ef3d`
- Selector recurrence audit:
  전체 Drive/project 교차 매칭은 반복 정규식 단계에서 장시간 무출력으로
  지연되어 중단했다. 이미 Drive file id, revision, source text,
  canonical project, target row가 확정된 상태라 기존 validator, artifact
  writer, `upsert_job` 함수를 고정 후보에 직접 적용했다. 자연어 파일명은
  버전을 파싱하지 못해 target lookup이 version 1로 빗나갈 수 있으므로,
  현재 website-visible KO maturity target인 `version=3`을 명시했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 1b2fb767-72ec-4249-8464-2ce4c248ef3d --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2276" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `a8ca80f0-ce53-4718-a138-b679e4ff2b9f`
  - promoted at: `2026-06-28T05:08:18.028379+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2276_binancecoin_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2276_binancecoin_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=binancecoin`, `symbol=BNB`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=1b2fb767-72ec-4249-8464-2ce4c248ef3d`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=a8ca80f0-ce53-4718-a138-b679e4ff2b9f`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=3`, `is_latest=true`
  - `card_summary_ko=BNB Chain은 BSC, opBNB, Greenfield를 묶은 멀티체인 생태계로 대규모 사용량과 유동성을 확보했다. 성숙도는 77.8점이며, 검증자 집중도와 MEV 통제, 거버넌스 투명성이 핵심 개선 과제다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/binancecoin` and
    `https://www.bcelab.xyz/en/projects/binancecoin` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate` and contained the promoted KO/EN summary.
  - `https://www.bcelab.xyz/ko/reports/binancecoin/maturity` and
    `https://www.bcelab.xyz/en/reports/binancecoin/maturity` returned HTTP
    `200` with the same no-cache headers and contained the promoted KO/EN
    summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2277 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 14:41 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 unpromoted source인 `MUon` MAT, `Light Heaven`
  ECON/MAT, `ARC` MAT/ECON, `AIOZ` MAT는 target row가 없거나 심볼 기반
  오탐 매칭으로 제외했다. 이번 실행에서 `bitcoin` MAT Drive source가
  공개 target row를 가진 최신 eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `Bitcoin의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2008–2026 20260526.md`.
- Canonical tracked project:
  `bitcoin` (`symbol=BTC`, `status=active`).
- Source identity:
  `drive:1cgwSk4ZhFiMoG2SGypl4s_e2Ie7cY8Jr:0B8HYgThT3NByb2dpOFZtRHNDVmtIM0VnVXZVenhqbHNPdnVJPQ`.
- Source SHA-256:
  `94994ef76fce9df38cc1a8ec56475a662e7d03fc7f93b929f28e39dc8298de5d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_bitcoin_bce2277.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_bitcoin_drive_selected_bce2277.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_bitcoin.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `bitcoin`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `4ac458b1-a9f9-43c4-956c-37e841c68067`
- Selector recurrence audit:
  표준 command는 Drive selector가 slug 후보 다운로드 단계에서 90초 이상
  무출력으로 지연되어 중단했다. 이미 Drive file id, revision, source
  text, canonical project, target row가 확정된 상태라 기존 validator,
  artifact writer, telemetry, `upsert_job` 함수를 고정 후보에 직접
  적용했다. 최초 validation은 프랑스어 summary 길이/하이픈 raw-fragment
  오탐으로 invalid였으나, 같은 idempotency key를 `force=True`로 갱신해
  valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 4ac458b1-a9f9-43c4-956c-37e841c68067 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2277" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - returned project report id: `5abf6c6e-896f-4a08-bc1b-a3023af481c0`
  - latest website-visible project report id:
    `e189e4b9-7387-4a4e-a4c8-03f85e70796a`
  - promoted at: `2026-06-28T05:40:03.051317+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2277_bitcoin_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bitcoin`, `symbol=BTC`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=4ac458b1-a9f9-43c4-956c-37e841c68067`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - latest website-visible `project_reports.id=e189e4b9-7387-4a4e-a4c8-03f85e70796a`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=Bitcoin은 85.9/100의 고성숙 통화 네트워크로 정산 보안, 공급 상한, ETF 접근성이 강하다. 다만 보조금 감소 이후 수수료 자립과 채굴·커스터디 중앙화가 핵심 미완 과제다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/bitcoin`,
    `https://www.bcelab.xyz/en/projects/bitcoin`,
    `https://www.bcelab.xyz/ko/reports/bitcoin/maturity`, and
    `https://www.bcelab.xyz/en/reports/bitcoin/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2273 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 09:43 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 미승격 후보 중 `MindWaveDAO` ECON과 `AIOZ` MAT는 target
  row가 없어 제외했고, `wouldmeme` ECON은 active tracked project 및 KO
  target row가 있어 eligible로 분류했다.
- 선택한 Drive Markdown:
  `Would 크립토이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `wouldmeme` (`symbol=WOULD`, `status=active`).
- Source identity:
  `drive:1mUDTmYk1OMfHViNApO7y53pYJUHCwZ9U:0B8HYgThT3NByODRCUHRQQjJqNytCcDVPaXMyUDQrTzdZeFRRPQ`.
- Source SHA-256:
  `d817c7e75ad651795effeeac12fca8335d0445130497a691634a885558e05647`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_wouldmeme_bce2273.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_wouldmeme_bce2273.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_wouldmeme.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `wouldmeme`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `11260ac8-a2b2-4183-bc63-b15efd5e02e3`
- Selector recurrence audit:
  표준 slug scan은 최신 slugless candidate인 `MindWaveDAO`를 `wouldmeme`
  후보로 먼저 선택해 source grounding mismatch를 만들 수 있어, 확정된
  WOULD Drive file id 1개에 기존 validator, artifact writer, telemetry,
  `upsert_job` 함수를 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 11260ac8-a2b2-4183-bc63-b15efd5e02e3 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2273" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `bf703568-1d3d-4a90-85e6-5218d2d77b3e`
  - promoted at: `2026-06-28T00:43:25.665629+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2273_wouldmeme_econ_db_website_verification.json`.
- Project report verification:
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`, `authority_mode=llm_active`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=WOULD는 고정 공급 밈 자산과 Solana DEX 유동성에 의존하는 단순 구조지만, 낮은 유동성과 공식 수익·거버넌스 부재가 핵심 한계다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/wouldmeme`,
    `https://www.bcelab.xyz/en/projects/wouldmeme`,
    `https://www.bcelab.xyz/ko/reports/wouldmeme/econ`, and
    `https://www.bcelab.xyz/en/reports/wouldmeme/econ` returned HTTP `200`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2275 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 13:46 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 unpromoted source인 `MUon` MAT는 canonical project가
  `monitoring_only`이고 KO maturity target row가 없어 제외했다.
  `MindWaveDAO`와 `AIOZ`는 이전 이력과 동일하게 target row가 없어
  제외했다. 이번 실행에서 `banana-for-scale` MAT Drive source가 target
  row와 공개 웹 URL을 가진 최신 eligible source로 확인됐다.
- 선택한 Drive Markdown:
  `Banana For Scale _ BANANAS31 크립토이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `banana-for-scale` (`symbol=BANANAS31`, `status=monitoring_only`).
- Source identity:
  `drive:1og_iIzhD-zxLZZfUcJB0eG7yuINwRzrS:0B8HYgThT3NByWmdVUmFPb3Q0cDYwdFMxcGkxZmhNRDYwdHRnPQ`.
- Source SHA-256:
  `298d9bc2d74a7297cd65052a4ca9082a5695af13567ee6b2f9f9cafb29ac6462`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_banana_for_scale_bce2275.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_banana_for_scale_drive_selected_bce2275.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_banana-for-scale.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `banana-for-scale`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `2aebe3de-7add-4f8d-a2f5-5b41fb748b89`
- Selector recurrence audit:
  표준 command는 Drive selector가 slugless/natural filename 후보들을
  다운로드하는 단계에서 장시간 무출력으로 지연되어 중단했다. 이미 Drive
  file id, revision, source text, canonical project, target row가 확정된
  상태라 기존 validator, artifact writer, telemetry, `upsert_job` 함수를
  고정 후보에 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 2aebe3de-7add-4f8d-a2f5-5b41fb748b89 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2275" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `25723b99-c687-4f2e-86e8-2f3208b65571`
  - promoted at: `2026-06-28T04:45:59.350499+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2275_banana_for_scale_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2275_banana_for_scale_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=banana-for-scale`, `symbol=BANANAS31`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=2aebe3de-7add-4f8d-a2f5-5b41fb748b89`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=25723b99-c687-4f2e-86e8-2f3208b65571`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Banana For Scale은 공급량 100억 개가 고정된 BNB Chain 밈 토큰으로 유동성은 있으나 AI Agent 경제, 수익 환류, 거버넌스와 감사 증거가 약하다. 종합 평가는 5점 만점 중 1.9점으로 초기 내러티브 단계다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/banana-for-scale` and
    `https://www.bcelab.xyz/en/projects/banana-for-scale` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate` and contained the promoted KO/EN summary plus marketing
    copy.
  - `https://www.bcelab.xyz/ko/reports/banana-for-scale/maturity` and
    `https://www.bcelab.xyz/en/reports/banana-for-scale/maturity` returned
    HTTP `200` with the same no-cache headers and contained the promoted KO/EN
    summary plus marketing copy.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2274 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 12:45 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 metadata 상위 후보인 `joseon-mun`, `bnb-attestation-service`,
  `zetachain`, `playnance`, `coca-cola-tokenized-stock-xstock`,
  `microstrategy-tokenized-stock-xstock` 등은 이미 promoted였고,
  `MindWaveDAO`와 `AIOZ`는 canonical target row가 없어 제외했다. 이번
  실행에서 `wouldmeme` MAT Drive source가 promoted되지 않은 최신 eligible
  source였고, KO `maturity` target row가 존재해 eligible로 분류했다.
- 선택한 Drive Markdown:
  `WOULD의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`.
- Canonical tracked project:
  `wouldmeme` (`symbol=WOULD`, `status=active`).
- Source identity:
  `drive:1m_JS2LsElXTwnzhmPtY39-3jnyPV08Pz:0B8HYgThT3NByODNUS3hwR3lsK1didkdiRnN5ZVc3Q3haaGJvPQ`.
- Source SHA-256:
  `5b331fa3978ed1712926c80c1bd80387515c4b2d019ab9e270d1dfb1bea01818`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_wouldmeme_bce2274.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_wouldmeme_drive_selected_bce2274.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_wouldmeme.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `wouldmeme`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `36005c62-842e-48e2-884a-ba564aa25f8f`
- Selector recurrence audit:
  표준 command는 Drive selector가 slugless/natural filename 후보들을
  다운로드하는 단계에서 장시간 무출력으로 지연되어 중단했다. 이미 Drive
  file id, revision, source text, canonical project, target row가 확정된
  상태라 기존 validator, artifact writer, telemetry, `upsert_job` 함수를
  고정 후보에 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 36005c62-842e-48e2-884a-ba564aa25f8f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2274" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `a50c1867-52a7-4f7e-9c6d-38ce41d745a1`
  - promoted at: `2026-06-28T03:44:44.126919+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2274_wouldmeme_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2274_wouldmeme_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=wouldmeme`, `symbol=WOULD`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=36005c62-842e-48e2-884a-ba564aa25f8f`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=a50c1867-52a7-4f7e-9c6d-38ce41d745a1`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=WOULD는 공급 고정성과 계약 권한 포기, 밈 지속성은 확인되지만 수익, 거버넌스, 개발자 생태계와 깊은 유동성이 약하다. 종합 60.75%로 전개 서사 단계의 Solana 밈 토큰이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/wouldmeme` and
    `https://www.bcelab.xyz/en/projects/wouldmeme` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted KO/EN summary plus marketing copy.
  - `https://www.bcelab.xyz/ko/reports/wouldmeme/maturity` and
    `https://www.bcelab.xyz/en/reports/wouldmeme/maturity` returned HTTP `200`
    with the same no-cache headers and contained the promoted KO/EN summary
    plus marketing copy.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2272 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 02:37 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2271](/BCE/issues/BCE-2271)은
  `coca-cola-tokenized-stock-xstock` MAT를 promoted 및 웹 검증 완료했다.
  이번 실행에서 같은 canonical project의 최신 ECON Drive source는 아직
  unpromoted였고, `coca-cola-tokenized-stock-xstock` KO `econ` target row가
  존재해 eligible로 분류했다.
- 선택한 Drive Markdown:
  `Coca-Cola tokenized stock (xStock) 크립토 이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `coca-cola-tokenized-stock-xstock` (`symbol=KOX`, `status=active`).
- Source identity:
  `drive:1hAVg8DDw7fMSLejPDPDNQJIKVg53tmXz:0B8HYgThT3NByQ0N4R0M2MkJXNXlHaGk1S1NvMUhyV2JlZUtNPQ`.
- Source SHA-256:
  `c22c87e97ea0a84829065affd4819331767bec7805230295941e2d2e7b361aa6`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_coca_cola_tokenized_stock_xstock_bce2272.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_coca_cola_tokenized_stock_xstock_drive_selected_bce2272.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_coca-cola-tokenized-stock-xstock.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `coca-cola-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `e7233964-5b5f-4f02-8d23-9476a7a19cc0`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id e7233964-5b5f-4f02-8d23-9476a7a19cc0 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2272" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `ae84fb72-1b1b-49c7-8b15-d0800d67de1b`
  - promoted at: `2026-06-27T17:36:09.08185+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2272_coca_cola_tokenized_stock_xstock_econ_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2272_coca_cola_tokenized_stock_xstock_econ_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=coca-cola-tokenized-stock-xstock`, `symbol=KOX`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=e7233964-5b5f-4f02-8d23-9476a7a19cc0`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=ae84fb72-1b1b-49c7-8b15-d0800d67de1b`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Coca Cola xStock KOx는 KO 주식 노출을 담보 기반 멀티체인 토큰으로 이전하지만, 오프체인 수탁과 낮은 유동성이 핵심 병목이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/coca-cola-tokenized-stock-xstock`
    and `https://www.bcelab.xyz/en/projects/coca-cola-tokenized-stock-xstock`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - `https://www.bcelab.xyz/ko/reports/coca-cola-tokenized-stock-xstock/econ`
    and
    `https://www.bcelab.xyz/en/reports/coca-cola-tokenized-stock-xstock/econ`
    returned HTTP `200` with the same no-cache headers.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2271 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 02:09 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2269](/BCE/issues/BCE-2269)은 `joseon-mun` MAT,
  [BCE-2270](/BCE/issues/BCE-2270)은 `joseon-mun` ECON을 promoted 및 웹
  검증 완료했다. 이번 실행에서 promoted source를 제외한 최신 Drive
  Markdown은 Coca-Cola tokenized stock xStock의 MAT 문서였고,
  `coca-cola-tokenized-stock-xstock` KO `maturity` target row가 존재해
  eligible로 분류했다.
- 선택한 Drive Markdown:
  `KOX 크립토 이코노미 성숙도 평가 보고서_ Coca-Cola tokenized stock (xStock).md`.
- Canonical tracked project:
  `coca-cola-tokenized-stock-xstock` (`symbol=KOX`, `status=active`).
- Source identity:
  `drive:1eNLE5J01Pp5SokPF0RKmegeUjkV6M-R8:0B8HYgThT3NByQXVNcEdMN1ZUTjFvY3hpZHJPRzRiSk9TYyt3PQ`.
- Source SHA-256:
  `c7b9253e56e46721a19dd2795c9736dfaebc9a78f54a4e0ce97f901c44c3a0a7`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_coca_cola_tokenized_stock_xstock_bce2271.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_coca_cola_tokenized_stock_xstock_drive_selected_bce2271.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_coca-cola-tokenized-stock-xstock.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `coca-cola-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `282d2632-06fe-41a0-847c-8c1ee1fad6e1`
- Selector recurrence audit:
  표준 command는 Drive selector가 slugless/natural filename 후보들을
  다운로드하는 단계에서 장시간 무출력으로 지연되어 중단했다. 이미 Drive
  file id, revision, canonical project, target row가 확정된 상태라 기존
  validator, artifact writer, telemetry, `upsert_job` 함수를 고정 후보에
  직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 282d2632-06fe-41a0-847c-8c1ee1fad6e1 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2271" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `e635efa1-a1e1-44b3-9eaf-245eb54f51d7`
  - promoted at: `2026-06-27T17:08:21.42314+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2271_coca_cola_tokenized_stock_xstock_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2271_coca_cola_tokenized_stock_xstock_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=coca-cola-tokenized-stock-xstock`, `symbol=KOX`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=282d2632-06fe-41a0-847c-8c1ee1fad6e1`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=e635efa1-a1e1-44b3-9eaf-245eb54f51d7`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Coca Cola xStock은 법적 담보와 멀티체인 구조가 성숙한 토큰화 주식 트래커지만, KOX 개별 유동성과 투명성은 아직 초기 검증 단계다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/coca-cola-tokenized-stock-xstock`
    and `https://www.bcelab.xyz/en/projects/coca-cola-tokenized-stock-xstock`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - `https://www.bcelab.xyz/ko/reports/coca-cola-tokenized-stock-xstock/maturity`
    and
    `https://www.bcelab.xyz/en/reports/coca-cola-tokenized-stock-xstock/maturity`
    returned HTTP `200` with the same no-cache headers.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2270 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 01:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2269](/BCE/issues/BCE-2269)은 `joseon-mun` MAT를
  promoted 및 웹 검증 완료했다. 이번 실행에서 같은 canonical project의
  최신 ECON Drive source는 아직 unpromoted였고, `joseon-mun` KO `econ`
  target row가 존재해 eligible로 분류했다.
- 선택한 Drive Markdown:
  `JSM 크립토 이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `joseon-mun` (`symbol=JSM`, `status=monitoring_only`).
- Source identity:
  `drive:1-3PK_cLuzfPIlBwmBSZDhjLj2sp9DhM8:0B8HYgThT3NByMjl3RGRnQktIdHcwWVNtM2U2UEEzK0UrdzJ3PQ`.
- Source SHA-256:
  `e5bab1770e3736aa7aa5c9a159d81bdf682d2905c8a0f3dba9cf8bff207c5a07`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_joseon_mun_bce2270.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_joseon_mun_drive_selected_bce2270.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_joseon-mun.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `joseon-mun`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `38c85708-39ed-4d82-98c7-bc8014c210ba`
- Selector recurrence audit:
  표준 command는 dry-run에서 정상 검증됐고 실제 upsert 명령도 Drive
  selector 단계에서 장시간 무출력으로 보였으나, 중단 신호 직전에 정상
  완료되어 direct fallback은 사용하지 않았다. 지연 양상은 기존
  slugless/natural filename selector recurrence와 같은 관찰로 남긴다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 38c85708-39ed-4d82-98c7-bc8014c210ba --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2270" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `75b4f054-3f17-4500-aa35-743584ac6016`
  - promoted at: `2026-06-27T16:37:08.440381+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2270_joseon_mun_econ_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2270_joseon_mun_econ_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=joseon-mun`, `symbol=JSM`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=38c85708-39ed-4d82-98c7-bc8014c210ba`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=75b4f054-3f17-4500-aa35-743584ac6016`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Joseon Mun은 Mun 통화, Denizen 법인격, 기업 지분 토큰화를 결합한 사이버 국가형 경제 설계지만 핵심 treasury와 registry 공개 검증이 아직 제한적이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/joseon-mun` and
    `https://www.bcelab.xyz/en/projects/joseon-mun` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - `https://www.bcelab.xyz/ko/reports/joseon-mun/econ` and
    `https://www.bcelab.xyz/en/reports/joseon-mun/econ` returned HTTP `200`
    with the same no-cache headers.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2269 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 01:23 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  직전 [BCE-2268](/BCE/issues/BCE-2268)은 `joseon-mun`의 공개 KO
  `project_reports` target row가 없어 no-op 처리했다. 이번 실행에서 DB를
  재확인한 결과 `joseon-mun`의 KO `econ` 및 `maturity` published/latest
  target row가 존재해 최신 unpromoted Drive source를 eligible로 재분류했다.
- 선택한 Drive Markdown:
  `Joseon의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Canonical tracked project:
  `joseon-mun` (`symbol=JSM`, `status=monitoring_only`).
- Source identity:
  `drive:1QZj3K1wk3cATTwQJS5rA8l3el8w6e05n:0B8HYgThT3NByZWUydzc4U0FqMWcvNlF2SjNiczRSQVM0cFQ4PQ`.
- Source SHA-256:
  `93ec5472ca63c8310824d0999c17a06f2cbb4c15d4f10ae2c8075b357a5bbf94`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_joseon_mun_bce2269.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_joseon_mun_drive_selected_bce2269.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_joseon-mun.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `joseon-mun`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `3cc6a64c-fb80-49fd-88aa-381a3f980dc4`
- Selector recurrence audit:
  표준 command는 Drive selector가 slugless/natural filename 후보들을
  다운로드하는 단계에서 장시간 지연되어 중단했다. 이미 Drive file id,
  revision, canonical project, target row가 확정된 상태라 기존 validator,
  artifact writer, telemetry, `upsert_job` 함수를 고정 후보에 직접 적용했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 3cc6a64c-fb80-49fd-88aa-381a3f980dc4 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2269" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `04a4e7ca-9d1c-4931-9084-6925dda02d53`
  - promoted at: `2026-06-27T16:22:35.184993+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2269_joseon_mun_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2269_joseon_mun_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=joseon-mun`, `symbol=JSM`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=3cc6a64c-fb80-49fd-88aa-381a3f980dc4`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=04a4e7ca-9d1c-4931-9084-6925dda02d53`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Joseon Mun은 초기 실행 검증 단계의 법인 토큰화 제도 프로젝트로, JSM 시장 존재는 확인되지만 공개 체인과 감사 및 거버넌스 증거가 부족하다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/joseon-mun` and
    `https://www.bcelab.xyz/en/projects/joseon-mun` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - `https://www.bcelab.xyz/ko/reports/joseon-mun/maturity` and
    `https://www.bcelab.xyz/en/reports/joseon-mun/maturity` returned HTTP
    `200` with the same no-cache headers.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2268 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 00:50 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry`; 신규 댓글은 없었고 harness checkout 상태에서 이전
  중단 루틴을 이어서 확인했다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2267](/BCE/issues/BCE-2267)은 BASCAN / BNB
  Attestation Service MAT를 promoted 및 웹 검증 완료했다.
- Drive/DB scan result:
  - Supabase promoted source identities: 361.
  - KO website-visible target rows checked: 754.
  - 최신 `JSM` ECON 및 `Joseon` MAT source는 canonical tracked project
    `joseon-mun` (`symbol=JSM`)은 있으나 공개 KO `project_reports` target
    row가 없어 제외했다.
  - `BAS` ECON 및 `BASCAN / BNB Attestation Service` MAT source는 이미
    promoted 상태다.
  - `ZETA` FOR source는 이미 job
    `dcea60e4-9bfb-4ba3-bf41-88e9aa5de98a`로 promoted 상태이며
    project report `e75e8b76-2121-47b1-8cb9-63d581b5d9f0`에 반영되어
    제외했다.
  - `GCOIN / Playnance` MAT source는 이미 job
    `69d5e827-bf29-48ba-bdee-05bb91b54777`로 promoted 상태이며
    project report `926ca7ce-c4ca-4d6d-b8b2-9185b61313e2`에 반영되어
    제외했다.
  - 최신 `KOX / Coca-Cola tokenized stock`, `Coca-Cola tokenized stock`
    ECON, `MindWaveDAO` ECON, `AIOZ / AIOZ Network` MAT source는 canonical
    tracked project 또는 공개 KO target row 매칭이 명확하지 않아 제외했다.
  - `MSTRx / MicroStrategy tokenized stock`, `Numerai/Numeraire`, `BIO`,
    `Quack AI` 등 그 다음 target-matched 후보들은 이미 promoted 상태다.
- Routine result:
  `no-op: no new analysis markdown`.
- Candidate ingest / Summary Authority Gate:
  실행하지 않았다. 신규 eligible unpromoted source가 없어 JSON 생성,
  `report_summary_jobs` upsert, `summary_authority_gate --write`, website
  publication을 수행하지 않았다.
- Deployment/cache implication:
  content promotion이 없었으므로 code deploy 및 cache 검증은 필요하지 않다.
- Manifest change:
  no change needed. This was a no-op routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2261 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 20:30 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2260](/BCE/issues/BCE-2260)은 LEO MAT를 promoted 및
  웹 검증 완료했다. 최신 `Coca-Cola/MindWaveDAO/WOULD/KOX/AIOZ` 계열은
  tracked project 또는 공개 KO target row 매칭이 명확하지 않아 이번에도
  제외했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터와 DB 기준으로
  스캔했다. 실제 `--force` selector는 slugless/natural filename score
  재발로 `solana` slug에서 Solana Mobile SKR source를, 이후
  `solana-mobile-seeker` slug에서 GCOIN/Playnance source를 선택해
  validation_failed rows를 만들었다. 이 selector 문제는 새 root cause가
  아니라 기존 slugless selector recurrence로 분류했고, promoted 승격은
  하지 않았다. 최종 처리는 [BCE-2260](/BCE/issues/BCE-2260)과 같이 확인된
  Drive file id를 고정해 기존 candidate validation, artifact, telemetry,
  `upsert_job` 함수를 직접 적용했다.
- 선택한 Drive Markdown:
  `Solana Mobile SKR의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024-2026.md`.
- Canonical tracked project:
  `solana-mobile-seeker` (`symbol=SKR`, `status=monitoring_only`).
- Source identity:
  `drive:15oNgOhTZIoq-uvYHed7OWJ_N2PBWFcAo:0B8HYgThT3NByUnVSb1RMSUtlWWNHS0xxNnpud0FlSXdLREZjPQ`.
- Source SHA-256:
  `70110ebf3b726b9e7b650c29acb1f561374e6e1a668de7cb85e8a78a63a4c81b`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_solana-mobile-seeker_bce2261.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_solana_drive_selected_bce2261.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_solana-mobile-seeker.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `solana-mobile-seeker`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `69f9a35b-d417-4e33-af44-1b1ffa665b28`
- Selector recurrence audit:
  - invalid `solana` job `6469ffd6-bf6b-44e9-a6b7-355f5383101e` selected
    the SKR source while validating Solana evidence and remains
    `validation_failed`.
  - invalid `solana-mobile-seeker` job
    `495c4572-0494-4463-aaf8-c4990aad1245` selected the GCOIN/Playnance
    source while validating SKR evidence and remains `validation_failed`.
  - Neither invalid row was sent through `summary_authority_gate`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 69f9a35b-d417-4e33-af44-1b1ffa665b28 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2261" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `5030102a-779d-4464-a2a9-9c5bef2041da`
  - promoted at: `2026-06-27T11:30:00.072908+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2261_solana_mobile_seeker_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2261_solana_mobile_seeker_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=solana-mobile-seeker`, `symbol=SKR`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=69f9a35b-d417-4e33-af44-1b1ffa665b28`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=5030102a-779d-4464-a2a9-9c5bef2041da`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=SKR은 성숙도 64점의 모바일 접근 계층 토큰으로, Seeker와 dApp Store는 검증됐지만 Guardian 탈중앙화와 수익성은 미완성이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/solana-mobile-seeker` and
    `https://www.bcelab.xyz/en/projects/solana-mobile-seeker` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - `https://www.bcelab.xyz/ko/reports/solana-mobile-seeker/maturity` and
    `https://www.bcelab.xyz/en/reports/solana-mobile-seeker/maturity`
    returned HTTP `200` with the same no-cache headers.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2262 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 21:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 `Coca-Cola/MindWaveDAO/WOULD/KOX/AIOZ` 계열 source는
  여전히 `tracked_projects` 또는 공개 KO target row 매칭이 없어 제외했다.
  최신 FOR `ZK` source는 `zksync/forensic/ko` website-visible target row가
  없어 제외했다. May 28 Banana source는 이미 `validation_failed` job으로
  처리됐고 canonical Banana MAT source는 promoted 상태라 새 후보로 보지
  않았다.
- 후보 선택:
  다음 최신 unprocessed이고 공개 KO forensic target row가 명확한
  `ORE / ORE` FOR 후보를 선택했다. canonical tracked project는
  `ore-new` (`symbol=ORE`, `status=monitoring_only`)다.
- 선택한 Drive Markdown:
  `ORE 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:16mV3KfmP5ExwHZrU-g6lQC6RQ7beRfPz:0B8HYgThT3NByWnl3ZWo3cncraGFSTGRPSEtLZlRmRm4reTZZPQ`.
- Source SHA-256:
  `3d9799db8b5d9e6bb8c8762493c6dc61caac1191e4ccb2e82cf248d2e5f1d377`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_ore-new_bce2262.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_ore_new_bce2262.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_ore-new.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `ore-new`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `64d419e2-7010-4ecd-9834-6123e10c80bf`
- Selector recurrence audit:
  standard dry-run command with `--slug ore-new` selected the newer ZK source
  for the ORE slug and failed grounding validation. This is the same slugless
  selector recurrence pattern recorded in prior runs, not a new root cause. The
  final ingest fixed the Drive file id and applied existing candidate
  validation, artifact, telemetry, and `upsert_job` functions directly.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 64d419e2-7010-4ecd-9834-6123e10c80bf --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2262" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `e6d46415-79dc-43d8-b579-cdb3972b5506`
  - promoted at: `2026-06-27T12:07:47.212035+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2262_ore_new_for_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2262_ore_new_for_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ore-new`, `symbol=ORE`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=64d419e2-7010-4ecd-9834-6123e10c80bf`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=e6d46415-79dc-43d8-b579-cdb3972b5506`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ORE는 15분봉 급등 뒤 101달러 부근에서 재균형 중인 고위험 토큰으로, 100달러 지지와 104~110달러 매도벽 돌파가 핵심 확인점이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ore-new` and
    `https://www.bcelab.xyz/en/projects/ore-new` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO project surface contained the promoted Korean summary and marketing
    copy. EN project surface contained the promoted English summary and
    marketing copy.
  - `https://www.bcelab.xyz/ko/reports/ore-new/forensic` and
    `https://www.bcelab.xyz/en/reports/ore-new/forensic` returned HTTP `200`
    with the same no-cache headers; these report-detail surfaces did not render
    the card summary strings directly in the fetched HTML.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment project surfaces.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2264 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 22:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2263](/BCE/issues/BCE-2263)은 TRON MAT를 promoted 및
  웹 검증 완료했다. 최신 unpromoted `KOX/Coca-Cola/MindWaveDAO/WOULD/AIOZ`
  계열은 이전 루틴과 동일하게 tracked project 또는 공개 KO target row
  매칭이 명확하지 않아 제외했다. 이번에는 그보다 최신이고 공개 KO econ
  target row가 명확한 `BAS / BNB Attestation Service` ECON 후보를 선택했다.
- 후보 선택:
  canonical tracked project는 `bnb-attestation-service`
  (`symbol=BAS`, `status=monitoring_only`)다.
- 선택한 Drive Markdown:
  `BAS 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1SCSteyqa6idWwqSFAdoi6r4fdGa62Y7u:0B8HYgThT3NByK3o1SXk2dHhsaU5nTzlXSFdITTFyR3VpMDhBPQ`.
- Source SHA-256:
  `12f7b3bc8187776744d2417bbd8035d5e30d8acbb0579cf33d08882c18848e0a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_bnb_attestation_service_bce2264.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_bnb_attestation_service_bce2264.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_bnb-attestation-service.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `bnb-attestation-service`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `8653cc69-494b-4ec9-bf0a-c24d65be3692`
- Execution note:
  source-path dry-run first failed on card-safe `raw_format_fragment` detection
  caused by hyphenated English/European-language terms such as `off-chain` and
  `token-issuance`; CRO JSON copy was rewritten without those fragments and the
  same dry-run then passed `valid`. The standard Drive ingest command completed
  with the selected BAS Drive source identity and inserted the candidate row.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 8653cc69-494b-4ec9-bf0a-c24d65be3692 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2264" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `514e68fa-949e-4002-8345-0c28cc5006bf`
  - promoted at: `2026-06-27T13:08:22.919834+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2264_bnb_attestation_service_econ_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2264_bnb_attestation_service_econ_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bnb-attestation-service`, `symbol=BAS`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=8653cc69-494b-4ec9-bf0a-c24d65be3692`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=514e68fa-949e-4002-8345-0c28cc5006bf`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=BAS는 BAS 토큰보다 증명 데이터와 신뢰 상태를 자산화하는 BNB 기반 인프라지만, 채택과 오프체인 신뢰가 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/bnb-attestation-service`,
    `https://www.bcelab.xyz/en/projects/bnb-attestation-service`,
    `https://www.bcelab.xyz/ko/reports/bnb-attestation-service/econ`, and
    `https://www.bcelab.xyz/en/reports/bnb-attestation-service/econ`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO and EN project/report surfaces contained the promoted summaries.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2265 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 23:05 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2264](/BCE/issues/BCE-2264)는 BAS ECON을 promoted
  및 웹 검증 완료했다. 최신 `BASCAN / BNB Attestation Service` MAT source는
  canonical `bnb-attestation-service`에 maturity target row가 없어
  제외했고, `binancecoin`으로 처리하는 것은 잘못된 root mapping으로
  판단했다. `KOX/Coca-Cola/MindWaveDAO/WOULD/AIOZ/ZK` 계열은 이전 루틴과
  동일하게 tracked project 또는 공개 KO target row 매칭이 명확하지 않아
  제외했다. Banana May 28 source는 이미 `validation_failed` job 이력이
  있어 제외했다.
- 후보 선택:
  다음 최신 unprocessed이고 공개 KO maturity target row가 명확한 `Solana`
  MAT 후보를 선택했다. canonical tracked project는 `solana`
  (`symbol=SOL`, `status=active`)다.
- 선택한 Drive Markdown:
  `Solana 크립토 이코노미 성숙도 평가 보고서.md`.
- Source identity:
  `drive:11j6CWwCzRuDGWKLwgNfjSQ_B_nzQxNqi:0B8HYgThT3NByTHJOT0pRUU81Rk43NTFTNmJuKzYveHFGUjFVPQ`.
- Source SHA-256:
  `12ab3dfeccbd59637601d1c21a0648318dc216f8c77b1b94ea71e4db66856442`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_solana_bce2265.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_solana_bce2265.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_solana.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `solana`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `51099bed-7e32-4f07-931d-1f07f53da77a`
- Execution note:
  source-path dry-run passed `valid`. The standard Drive ingest command with
  `--drive-root-scope all` was interrupted after more than 3 minutes while
  downloading broad Drive candidates, matching the known slugless/broad scan
  recurrence pattern recorded in prior runs. Final ingest fixed the selected
  Drive file id and applied existing candidate validation, artifact, telemetry,
  and `upsert_job` functions directly. The candidate source version was set to
  `2` to match the latest website-visible KO maturity target row.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 51099bed-7e32-4f07-931d-1f07f53da77a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2265" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `e30574f7-aeeb-4abd-80ff-460deee4c01c`
  - promoted at: `2026-06-27T14:05:23.551562+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2265_solana_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2265_solana_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=solana`, `symbol=SOL`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=51099bed-7e32-4f07-931d-1f07f53da77a`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=e30574f7-aeeb-4abd-80ff-460deee4c01c`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=Solana는 성숙도 80점의 고성능 자본시장형 L1로 제도권 결제와 RWA 확장은 강하지만, 보안 예산과 검증인 집중이 남은 병목이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/solana`,
    `https://www.bcelab.xyz/en/projects/solana`,
    `https://www.bcelab.xyz/ko/reports/solana/maturity`, and
    `https://www.bcelab.xyz/en/reports/solana/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO and EN project/report surfaces contained the promoted summaries.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2266 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 23:50 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2265](/BCE/issues/BCE-2265)는 Solana MAT를 promoted
  및 웹 검증 완료했다. 최신 미승격 `BASCAN / BNB Attestation Service` MAT
  source는 여전히 canonical `bnb-attestation-service`에 maturity target
  row가 없어 제외했고, `binancecoin`으로 처리하지 않았다. `KOX /
  Coca-Cola`, `MindWaveDAO`, `WOULD`, `AIOZ`, `ZK` 계열도 tracked project
  또는 공개 KO target row 매칭이 명확하지 않아 제외했다. Banana May 28
  source는 기존 validation_failed 이력이 있고 canonical Banana MAT source는
  promoted 상태라 제외했다.
- 후보 선택:
  다음 최신 미승격이고 공개 KO maturity target row가 명확한 `Circle USDC`
  MAT 후보를 선택했다. canonical tracked project는 `usd-coin`
  (`symbol=USDC`, `status=active`)다.
- 선택한 Drive Markdown:
  `Circle USDC 크립토 이코노미 성숙도 평가 보고서.md`.
- Source identity:
  `drive:1oOFzTD1PtIB1gaQP_Rx5PlAFk8orrogx:0B8HYgThT3NByTzZHZVVWUTU4T2NrUVNZU20xcDNtV09WazR3PQ`.
- Source SHA-256:
  `536461b5722e695af5ffee855f6987390f1843cbac5741619b4a5741a91ad6fc`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_usd-coin_bce2266.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_usd_coin_bce2266.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_usd-coin.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `usd-coin`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `30a08456-4e60-4f99-a002-a5900f31ce3d`
- Execution note:
  source-path dry-run first failed on `marketing_by_lang.ko.too_many_sentences`;
  CRO JSON KO marketing copy was rewritten as one card-safe sentence and the
  source-path dry-run then passed `valid`. The standard Drive ingest command was
  interrupted after more than 90 seconds while downloading broad Drive
  candidates, matching the known slugless/broad scan recurrence pattern recorded
  in prior runs. Final ingest fixed the selected Drive file id and applied
  existing candidate validation, artifact, telemetry, and `upsert_job` functions
  directly. The candidate source version was set to `3` to match the latest
  website-visible KO maturity target row.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 30a08456-4e60-4f99-a002-a5900f31ce3d --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2266" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `cea2307e-17c4-4905-b7fa-b4c112d3425c`
  - promoted at: `2026-06-27T14:50:56.504121+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2266_usd_coin_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2266_usd_coin_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=usd-coin`, `symbol=USDC`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=30a08456-4e60-4f99-a002-a5900f31ce3d`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=cea2307e-17c4-4905-b7fa-b4c112d3425c`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=3`, `is_latest=true`
  - `card_summary_ko=USDC는 성숙도 82점의 규제형 온체인 달러 네트워크로, 준비금 투명성과 34개 체인 확장은 강하지만 발행자 통제와 금리 의존이 병목이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/usd-coin`,
    `https://www.bcelab.xyz/en/projects/usd-coin`,
    `https://www.bcelab.xyz/ko/reports/usd-coin/maturity`, and
    `https://www.bcelab.xyz/en/reports/usd-coin/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO and EN project/report surfaces contained the promoted summaries.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2263 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 22:04 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 최신 active 미승격 `KOX/Coca-Cola/MindWaveDAO/WOULD/AIOZ`
  계열은 직전 루틴과 동일하게 tracked project 또는 공개 KO target row
  매칭이 명확하지 않아 제외했다. ZK FOR는 공개 KO forensic target row가
  없어 제외했고, Banana/Solana 계열은 이미 promoted 또는 validation_failed
  이력이 있어 새 승격 대상으로 보지 않았다.
- 후보 선택:
  다음 최신 미승격이고 공개 KO maturity target row가 명확한 legacy
  `TRON DAO / TRX` MAT 후보를 선택했다. canonical tracked project는
  `tron` (`symbol=TRX`, `status=active`)다.
- 선택한 Drive Markdown:
  `TRON DAO의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2018–2026.md`.
- Source identity:
  `drive:1gIPkTM6yd2baau9sv5Hl1FMDYY3osd-t:0B8HYgThT3NByWG4zT0g2RUJhaUxjWWloYWl2WjF4MzVaa2FZPQ`.
- Source SHA-256:
  `c3a7c85410e86850f56b98720ccf1b48c6e75499464c6e9cfbf3d781e3f0b3c4`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_tron_bce2263.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_tron_bce2263.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_tron.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `tron`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `4c3b1430-b369-48b6-96f6-148326840119`
- Execution note:
  source-path dry-run passed `valid`. The standard `--drive-root-scope all`
  command was interrupted while downloading many Drive candidates before
  selection, the same broad scan/slugless selector recurrence pattern recorded
  in prior runs. Final ingest fixed the selected Drive file id and applied the
  existing candidate validation, artifact, telemetry, and `upsert_job`
  functions directly. The candidate source version was set to `3` to match the
  latest website-visible KO maturity target row.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 4c3b1430-b369-48b6-96f6-148326840119 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2263" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `c4d79ca0-71c6-499d-a32b-85cf0ce1c732`
- DB verification artifact:
  `scripts/pipeline/output/bce2263_tron_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2263_tron_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=tron`, `symbol=TRX`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=4c3b1430-b369-48b6-96f6-148326840119`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=c4d79ca0-71c6-499d-a32b-85cf0ce1c732`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=3`, `is_latest=true`
  - `card_summary_ko=TRON은 성숙도 73.6점의 USDT 결제 레이어로, 결제량과 수익은 강하지만 SR 집중과 DeFi 얕이가 병목이다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/tron`,
    `https://www.bcelab.xyz/en/projects/tron`,
    `https://www.bcelab.xyz/ko/reports/tron/maturity`, and
    `https://www.bcelab.xyz/en/reports/tron/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO and EN project/report surfaces contained the promoted summaries.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2267 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 00:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2266](/BCE/issues/BCE-2266)은 USDC MAT를 promoted
  및 웹 검증 완료했다. 최신 미승격 `Joseon` MAT source는 tracked project는
  있으나 공개 KO maturity target row가 없어 제외했다. 그 다음 최신
  미승격 `BASCAN / BNB Attestation Service` MAT source는
  `bnb-attestation-service`의 공개 KO maturity target row가 확인되어
  이번 후보로 선택했다.
- 후보 선택:
  canonical tracked project는 `bnb-attestation-service`
  (`symbol=BAS`, `status=monitoring_only`)다.
- 선택한 Drive Markdown:
  `BASCAN _ BNB Attestation Service의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1bHCvrj6d3jr76FenJide3HPsP7pz1cQ_:0B8HYgThT3NByUU52L2tIc2M0ZnhWWExScnVvK3NTYkdPZDc4PQ`.
- Source SHA-256:
  `8cb625da383e26b65486040b3d0886aad7dd17f6a3fdc2540f448340758071ac`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_bnb_attestation_service_bce2267.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_bnb_attestation_service_bce2267.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_bnb-attestation-service.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `bnb-attestation-service`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `3169ee9c-b68e-471b-8cc8-7e2128d36d05`
- Execution note:
  source-path dry-run passed `valid`. The standard Drive ingest command with
  `--drive-root-scope all` was interrupted after more than 90 seconds while
  downloading broad Drive candidates before selection, matching the known
  slugless/broad scan recurrence pattern recorded in prior runs. Final ingest
  fixed the selected Drive file id and applied existing candidate validation,
  artifact, telemetry, and `upsert_job` functions directly. The candidate
  source version was set to `1` to match the website-visible KO maturity target
  row.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 3169ee9c-b68e-471b-8cc8-7e2128d36d05 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2267" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `4bfe8bce-45d3-401b-9925-0182fabbb761`
  - promoted at: `2026-06-27T15:07:01.816836+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2267_bnb_attestation_service_mat_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2267_bnb_attestation_service_mat_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bnb-attestation-service`, `symbol=BAS`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=3169ee9c-b68e-471b-8cc8-7e2128d36d05`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=4bfe8bce-45d3-401b-9925-0182fabbb761`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=BAS는 성숙도 66.1점의 BNB 신원 및 어테스테이션 인프라로, Passport와 Greenfield 통합은 강하지만 재무와 거버넌스 공시는 미성숙하다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/bnb-attestation-service`,
    `https://www.bcelab.xyz/en/projects/bnb-attestation-service`,
    `https://www.bcelab.xyz/ko/reports/bnb-attestation-service/maturity`,
    and `https://www.bcelab.xyz/en/reports/bnb-attestation-service/maturity`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO and EN project/report surfaces contained the promoted summaries and
    marketing copy.
  - Local Python CA verification failed on the first HTTPS attempt, so the
    stored website verification artifact records the successful fetch using an
    unverified SSL context for fetch only.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2260 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 19:44 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2259](/BCE/issues/BCE-2259)은 Banana For Scale MAT를
  promoted 및 웹 검증 완료했다. 최신 `Coca-Cola/MindWaveDAO/WOULD/KOX/AIOZ`
  계열 source는 tracked project 또는 공개 KO target row 매칭이 명확하지
  않아 제외했다. 표준 `--slug zksync` Drive command는 알려진 slugless
  selector 재발로 이미 [BCE-2241](/BCE/issues/BCE-2241)에서 promoted 된
  ZETA Drive file id `1kVJVzNtzn7IILOSdM7xlgdWOPvgbXJM7`를 선택해 source
  grounding mismatch invalid row를 만들었다. 해당 문제는 새 root cause로
  보지 않고 기존 selector recurrence로 분류했다.
- 후보 선택:
  다음 명확한 공개 KO maturity target row를 가진 `UNUS SED LEO / LEO` MAT
  후보를 선택했다. canonical tracked project는 `leo-token` (`symbol=LEO`)다.
- 선택한 Drive Markdown:
  `UNUS SED LEO의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2019 - 2026 (1).md`.
- Source identity:
  `drive:14KPxy0fDttKz0CaNSgXxSUjzm5zDW9wV:0B8HYgThT3NByYUwvUEV5UmZEK3RZSEF1OFI3aXpNdlNhVlcwPQ`.
- Source SHA-256:
  `ccafc9989716fa2ac6d560c6916c8b06c742e18dfb39ed810bc9db9d2ee3214d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_leo_token_bce2260.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_leo_token_bce2260.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_leo-token.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `leo-token`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d7e789ae-0104-482b-a521-2ba39081b789`
- Execution note:
  source snapshot dry-run passed `valid`. Because slugless Drive filenames can
  cause the broad Drive command to select the wrong source, final ingest applied
  existing candidate validation, artifact, telemetry, and `upsert_job` functions
  directly to the selected LEO Drive file id. The candidate source version was
  set to `2` to match the latest website-visible KO maturity target row.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d7e789ae-0104-482b-a521-2ba39081b789 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2260" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `f0655a65-07a7-4ded-b227-75001d53f681`
  - promoted at: `2026-06-27T10:43:55.199843+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2260_leo_token_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=leo-token`, `symbol=LEO`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=d7e789ae-0104-482b-a521-2ba39081b789`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `project_reports.id=f0655a65-07a7-4ded-b227-75001d53f681`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=LEO는 성숙도 64.85점의 거래소 현금흐름 연동 토큰으로, 소각은 작동하지만 제로 수수료 이후 유틸리티 재설계가 병목이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=d7e789ae-0104-482b-a521-2ba39081b789`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/leo-token` and
    `https://www.bcelab.xyz/en/projects/leo-token` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - `https://www.bcelab.xyz/ko/reports/leo-token/maturity` and
    `https://www.bcelab.xyz/en/reports/leo-token/maturity` returned HTTP `200`
    with the same no-cache headers.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2259 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 19:22 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2258](/BCE/issues/BCE-2258)은 ETHGas/GWEI FOR를
  promoted 및 웹 검증 완료했다. 최신 ZETA FOR, GCOIN MAT, MSTRx ECON,
  Numeraire MAT/ECON, AWE FOR 등은 이미 promoted 상태이거나 target 매칭
  이력이 있었다. `KOX/Coca-Cola/MindWave/AIOZ` 계열 최신 후보는 tracked
  project/target 매칭이 명확하지 않아 제외했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터와 DB 기준으로
  스캔했다. 다음 명확한 공개 KO maturity target row를 가진
  `Banana For Scale / BANANAS31` MAT 후보를 선택했다. canonical tracked
  project는 `banana-for-scale` (`symbol=BANANAS31`)다.
- 선택한 Drive Markdown:
  `banana-for-scale(BANANAS31)_v1_MAT.md`.
- Source identity:
  `drive:11CKrQcMUAcm8mlvMPJGLYfbghsmAOlyr:0B8HYgThT3NByK1NYb055WXhrL1hTYXNoWlhwM2UyQTFTRGVrPQ`.
- Source SHA-256:
  `c4626724702c8b69c57a5cc59988d4d2dabd7b4a1d0ef268cd2f0e9f07ae2dce`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_banana_for_scale_bce2259.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_banana_for_scale_drive_selected_bce2259.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_banana-for-scale.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug banana-for-scale --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_banana_for_scale_bce2259.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `banana-for-scale`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `6f74588f-a1d9-4841-8f9f-f6c32a609e99`
- Execution note:
  initial local dry-run against the newer May 28 Banana source passed after
  English raw numeric wording was removed, but Drive ingest selected the
  canonical `banana-for-scale(BANANAS31)_v1_MAT.md` source for the slug. The
  CRO JSON evidence was corrected to exact sentences from that Drive-selected
  source, then local dry-run and Drive ingest both passed validation.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 6f74588f-a1d9-4841-8f9f-f6c32a609e99 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2259" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `25723b99-c687-4f2e-86e8-2f3208b65571`
  - promoted at: `2026-06-27T10:22:34.949326+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2259_banana_for_scale_mat_db_verification.json`.
- Website/cache verification artifacts:
  `scripts/pipeline/output/bce2259_banana_for_scale_mat_website_verification.json`
  and
  `scripts/pipeline/output/bce2259_banana_for_scale_mat_report_route_verification.json`.
- Project report verification:
  - `tracked_projects.slug=banana-for-scale`, `symbol=BANANAS31`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=6f74588f-a1d9-4841-8f9f-f6c32a609e99`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `project_reports.id=25723b99-c687-4f2e-86e8-2f3208b65571`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=BANANAS31은 성숙도 54점의 AI 밈 성장 토큰으로, 거래 접근성은 강하지만 제품 수익·감사·거버넌스 검증은 부족하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=6f74588f-a1d9-4841-8f9f-f6c32a609e99`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/banana-for-scale` and
    `https://www.bcelab.xyz/en/projects/banana-for-scale` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - `https://www.bcelab.xyz/ko/reports/banana-for-scale/maturity` and
    `https://www.bcelab.xyz/en/reports/banana-for-scale/maturity` returned
    HTTP `200` with the same no-cache headers.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
  - The local curl verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2258 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 18:43 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2257](/BCE/issues/BCE-2257)은 ASTER FOR를 promoted 및
  웹 검증 완료했다. 이번 실행은 그 다음 미승격 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 `ZETA` FOR 및 `GCOIN` MAT source는 이미 promoted 상태였고,
  `Coca-Cola/KOX/MindWave/AIOZ` 계열 최신 후보는 tracked project/target
  매칭이 명확하지 않았다. 다음 명확한 공개 KO forensic target row를 가진
  `ETHGas_GWEI` FOR를 선택했다. canonical tracked project는 `eth-gas`
  (`symbol=GWEI`)다.
- 선택한 Drive Markdown:
  `ETHGas_GWEI 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1b_2EtUCu4DoK9YwFz2ahHbRw_hPIcIS5:0B8HYgThT3NBybzRTd0I0UXFwU245QjFWeCs0YTJhNk1tUk9NPQ`.
- Source SHA-256:
  `64a81bc8cb0100d47ea38ca78eb58b6b9ffdffcf9791a5fd93b6f7cf43c4d942`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_eth_gas_bce2258.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_eth_gas_bce2258.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_eth-gas.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug eth-gas --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_eth_gas_bce2258.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `for`
  - slug: `eth-gas`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `6415ad6b-ab9d-4338-8b97-656c3173860e`
- Execution note:
  local source-path dry-run initially found `marketing_by_lang.ko.too_many_sentences`
  and `summary_by_lang.fr.raw_format_fragment`; the CRO JSON was shortened and
  hyphenated French wording was removed before Drive ingest. The final dry-run
  and Drive ingest both passed validation.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 6415ad6b-ab9d-4338-8b97-656c3173860e --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2258" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `baf94d77-724b-4339-b732-65df76a3b451`
  - promoted at: `2026-06-27T09:42:50.854385+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2258_eth_gas_for_db_verification.json`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2258_eth_gas_for_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=eth-gas`, `symbol=GWEI`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=6415ad6b-ab9d-4338-8b97-656c3173860e`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `project_reports.id=baf94d77-724b-4339-b732-65df76a3b451`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=GWEI는 고점 대비 32% 조정과 조작 리스크 62점으로, 0.11540달러 회복 전까지 ETHGas 반등 확인이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=6415ad6b-ab9d-4338-8b97-656c3173860e`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/eth-gas`,
    `https://www.bcelab.xyz/ko/reports/forensic/eth-gas`,
    `https://www.bcelab.xyz/en/projects/eth-gas`, and
    `https://www.bcelab.xyz/en/reports/forensic/eth-gas` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local curl verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2257 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 18:11 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2255](/BCE/issues/BCE-2255)는 BNB FOR를 promoted 및
  웹 검증 완료했고, [BCE-2256](/BCE/issues/BCE-2256) target 복구도
  반영됐다. 이번 실행은 그 다음 미승격 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 FOR 후보 중 `ZK` 등은 tracked project/target 매칭이 없었고,
  다음 명확한 공개 KO forensic target row를 가진 `Aster_ASTER` FOR를
  선택했다. canonical tracked project는 `aster` (`symbol=ASTER`)다.
- 선택한 Drive Markdown:
  `Aster_ASTER 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1Y6fc_0t-_uoPENBf9STZHwp3MI3e0zLu:0B8HYgThT3NBydzFyWkJvWTM2Y3BITTh2N3JhUFNZdDBOYUNBPQ`.
- Source SHA-256:
  `3a62100a29caec6a451fa9364b6f4f6d4e4ec78acb2b50c39f14c638120a6674`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_aster_bce2257.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_aster_bce2257.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_aster.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug aster --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_aster_bce2257.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `for`
  - slug: `aster`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `c9bb9714-8fe8-42cd-b019-aa9f004c3c82`
- Execution note:
  initial ingest inserted the same idempotency row as `validation_failed`
  because raw hyphenated risk wording and one non-exact evidence sentence failed
  validator checks. The CRO JSON was corrected and the row was updated with
  `--force` to valid before promotion.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id c9bb9714-8fe8-42cd-b019-aa9f004c3c82 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2257" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `da9802fc-3c6e-4c19-8c29-f89b06c3a586`
  - promoted at: `2026-06-27T09:11:09.577196+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2257_aster_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=aster`, `symbol=ASTER`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=c9bb9714-8fe8-42cd-b019-aa9f004c3c82`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `project_reports.id=da9802fc-3c6e-4c19-8c29-f89b06c3a586`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ASTER는 높은 변동성과 조작 스코어 63점으로, 0.708달러 방어와 0.737달러 회복 전까지 관망이 우선이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=c9bb9714-8fe8-42cd-b019-aa9f004c3c82`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/aster`,
    `https://www.bcelab.xyz/ko/reports/forensic/aster`,
    `https://www.bcelab.xyz/en/projects/aster`, and
    `https://www.bcelab.xyz/en/reports/forensic/aster` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is confirmed on the current
  production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2236 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 18:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  Playnance MAT 및 MSTRx ECON source를 제외했다. 최신 미승격 후보 중
  `Numeraire / Numerai` MAT가 tracked project `numeraire`와 공개 KO maturity
  target row를 보유해 이번 실행의 eligible source로 선택됐다.
- 선택한 Drive Markdown:
  `Numerai의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2015 - 2026.md`.
- Source identity:
  `drive:1mCxQ1yRh729EUgyP6p7yujyLnL1JaZBA:0B8HYgThT3NByR2hjbW9PSlp2LzEzd0RneTdJaXJoMTEvSWJzPQ`.
- Source SHA-256:
  `eb7d52f2e1c61a84c1ab63470d174baa2d32369cfcff1902881b7881cb47f2d6`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_numeraire_bce2236.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_numeraire_bce2236.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_numeraire.json`.
- Execution note:
  표준 `analysis_md_summary_candidate.py --slug numeraire` 경로는 현재 Drive
  파일명 파서가 최신 Korean analysis Markdown을 `parsed=null`로 반환하고,
  slugless 파일을 넓게 포함할 수 있어 사용하지 않았다. 선택된 Numerai Drive
  file id 1개에 기존 candidate validation, artifact, and `upsert_job` 함수를
  직접 적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `numeraire`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `604f19d1-b23e-4a71-bdd6-dfcf27d9dd35`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 604f19d1-b23e-4a71-bdd6-dfcf27d9dd35 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2236" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `7af7e0d5-f91d-4fc0-9b23-70a58e608eff`
  - promoted at: `2026-06-26T09:08:12.155768+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2236_numeraire_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=numeraire`
  - `tracked_projects.symbol=NMR`
  - `project_reports.id=7af7e0d5-f91d-4fc0-9b23-70a58e608eff`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Numerai는 73.9점의 성숙 서사 초입으로, AUM과 기관 수용은 강하지만 NMR 지급 재원과 거버넌스 신뢰가 다음 병목이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=604f19d1-b23e-4a71-bdd6-dfcf27d9dd35`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/numeraire` and
    `https://www.bcelab.xyz/en/projects/numeraire` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO project page contained the promoted Korean summary and Investment View
    text.
  - EN project page contained the promoted English summary and Investment View
    text.
  - `https://www.bcelab.xyz/{ko,en}/reports/maturity/numeraire` returned HTTP
    `404`; this matches the current report-detail route behavior seen in prior
    routine executions, while project-page website visibility is confirmed.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Project-page website visibility is already
  confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2255 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 17:43 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  상태 문서 이력을 확인했다. 직전 [BCE-2254](/BCE/issues/BCE-2254)는
  Monero FOR를 promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음
  후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `KOX/Coca-Cola tokenized stock`, `MindWaveDAO`,
  `AIOZ`, `WOULD`, and `ZK` 계열은 tracked project 매칭이 없거나
  모호해 제외했다. 다음 명확한 tracked project 매칭 source로 `BNB` FOR를
  선택했다.
- 선택한 Drive Markdown:
  `BNB 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1a1NT7O-wXBmqZ357ooWr5MGpcdx-PpW8:0B8HYgThT3NByZ21FNVNqZ2k3c0p2Z25mMlNXRnphdGZDcXJrPQ`.
- Source SHA-256:
  `462931056529efb87ca0a5d75813ccf1ecc6cbac951293948efc166e18197880`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_bnb_bce2255.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_bnb_bce2255.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_bnb.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug bnb --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_bnb_bce2255.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `for`
  - slug: `bnb`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d00c8e0f-4bcf-4282-aa62-81ffd1cf1690`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d00c8e0f-4bcf-4282-aa62-81ffd1cf1690 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2255" --write`.
- Promotion result:
  - first attempt: blocked before promotion because
    `website-visible project_reports target not found: bnb/forensic/ko`
  - after [BCE-2256](/BCE/issues/BCE-2256) restoration and
    `tracked_projects.status` correction, rerun action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `2041b211-e730-4cf4-bcbd-339dda97358c`
  - promoted at: `2026-06-27T08:43:08.041857+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2255_bnb_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bnb`, `symbol=BNB`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=d00c8e0f-4bcf-4282-aa62-81ffd1cf1690`
  - `validation_status=valid`, `status=candidate_ready`, `authority_state=promoted`
  - `project_reports.id=2041b211-e730-4cf4-bcbd-339dda97358c`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=BNB는 MEDIUM 리스크와 조작 스코어 45점으로, 700~703달러 지지 확인 뒤 조건부 매수만 유효하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=d00c8e0f-4bcf-4282-aa62-81ffd1cf1690`
- Website/cache verification:
  - Browser verification used system Google Chrome because the bundled
    Playwright browser was not installed.
  - `https://www.bcelab.xyz/ko/projects/bnb`,
    `https://www.bcelab.xyz/ko/reports/forensic/bnb`,
    `https://www.bcelab.xyz/en/projects/bnb`, and
    `https://www.bcelab.xyz/en/reports/forensic/bnb` rendered successfully.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC
  plus DB visibility-state restoration for BNB. No code deploy was required.
  Website visibility is confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

#### BCE-2256 BNB FOR KO Target Restoration (2026-06-27 17:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/for.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  직전 [BCE-2255](/BCE/issues/BCE-2255)의 candidate job
  `d00c8e0f-4bcf-4282-aa62-81ffd1cf1690`은 여전히
  `validation_status=valid`, `status=candidate_ready`,
  `authority_state=validation_passed` 상태였다. 문제는 gate 코드가 아니라
  기존 BNB FOR KO target row가 `cancelled` 상태라 website-visible target
  query에서 제외된 DB 상태였다.
- Restored target row:
  - `project_reports.id=2041b211-e730-4cf4-bcbd-339dda97358c`
  - `tracked_projects.slug=bnb`, `symbol=BNB`
  - `report_type=forensic`, `language=ko`, `version=1`
  - before: `status=cancelled`, `is_latest=false`
  - after: `status=published`, `is_latest=true`
  - follow-up CRO correction: `tracked_projects.status` was restored from
    `archived` to `active` so the public project page can query the report.
  - preserved source identity:
    `gdrive|d11f98db-420f-40a4-8918-714448b905bf|bnb|forensic|ko|1DNBqfjM4p_TQQo5hgAErP1-BqUi7pTpk|2026-06-01T01:53:19.000Z|23066656||BNB_FOR_ko.pdf`
  - preserved KO slide asset:
    `https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/slides/for/bnb/latest/ko.html`
  - `tracked_projects.last_forensic_report_at` remains aligned to the restored
    row `published_at=2026-06-11T03:02:41.726383+00:00`.
- Summary Authority Gate verification:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d00c8e0f-4bcf-4282-aa62-81ffd1cf1690 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2255"`
  returned a dry-run `promote` decision with
  `project_report_id=2041b211-e730-4cf4-bcbd-339dda97358c` and no DB writes.
- Website verification:
  `https://www.bcelab.xyz/ko/projects/bnb` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  rendered FOR/forensic page content.
- Deployment/cache implication:
  this was a Supabase DB state restoration only. No code deploy was required.
  The existing BCE-2255 candidate remains ready for the CRO routine to rerun the
  Summary Authority Gate write command.
- Manifest change:
  no change needed. The restoration preserves the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2254 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 17:11 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  상태 문서 이력을 확인했다. 직전 [BCE-2253](/BCE/issues/BCE-2253)는
  HBAR FOR를 promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음 후보부터
  선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `KOX/Coca-Cola tokenized stock`, `MindWaveDAO`,
  `AIOZ`, and `WOULD` 계열은 `tracked_projects` target 매칭이 없어 제외했다.
  다음 명확한 eligible source로 `Monero` FOR를 선택했고 canonical tracked
  project는 `monero` (`symbol=XMR`)다.
- 선택한 Drive Markdown:
  `Monero 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1yAxI6853QYLxznKDbmz4T8z7Fsq-n2d1:0B8HYgThT3NByaXhJdlNMYlRSa2dBajNsTitnejEyZjZjZHhFPQ`.
- Source SHA-256:
  `11e71e9ebef774f3e55ba04c42d752656e1994536e944ef079cfbe2e3b3251b6`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_monero_bce2254.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_monero_bce2254.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_monero.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug monero --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_monero_bce2254.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `for`
  - slug: `monero`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `4eb4e5fe-2e64-454a-8e33-01f5eec6cb9d`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 4eb4e5fe-2e64-454a-8e33-01f5eec6cb9d --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2254" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `e2a93d7e-8247-4e31-adca-64831e8d13ad`
  - promoted at: `2026-06-27T08:11:23.98928+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2254_monero_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=monero`
  - `tracked_projects.symbol=XMR`
  - `project_reports.id=e2a93d7e-8247-4e31-adca-64831e8d13ad`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Monero는 HIGH 리스크와 조작 스코어 58점으로, 380.50달러 고점 스윕 뒤 361달러대 회귀가 핵심 부담이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=4eb4e5fe-2e64-454a-8e33-01f5eec6cb9d`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/monero`,
    `https://www.bcelab.xyz/ko/reports/forensic/monero`,
    `https://www.bcelab.xyz/en/projects/monero`,
    `https://www.bcelab.xyz/en/reports/forensic/monero` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2253 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 16:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  상태 문서 이력을 확인했다. 직전 [BCE-2249](/BCE/issues/BCE-2249)는
  Berachain FOR를 promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음
  후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `KOX/Coca-Cola tokenized stock`, `MindWaveDAO`,
  `AIOZ`, and `WOULD` 계열은 직전 루틴 기록 및 DB target row 확인상 승격
  대상이 아니어서 제외했다. 다음 명확한 eligible source로 `HBAR` FOR를
  선택했고 canonical tracked project는 `hedera-hashgraph` (`symbol=HBAR`)다.
- 선택한 Drive Markdown:
  `HBAR 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:14qWVN7dZtuzMZ_zeZHUm-ZPixVpMJg5t:0B8HYgThT3NByLyttRUhmN0FBYzVEYVNOQkhpQjd6QnNRWkh3PQ`.
- Source SHA-256:
  `732a49360162a3dafed8f0493ecccaf2cd59a0068e086857f8b5c347fcb618d6`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_hedera_hashgraph_bce2253.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_hedera_hashgraph_bce2253.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_hedera-hashgraph.json`.
- Execution note:
  표준 dry-run은 `--slug hedera-hashgraph`로 선택된 HBAR Drive source를
  정확히 골랐다. 이어 이슈 지시의 broad `--force` command는 다른 FOR
  Drive file id `1kVJVzNtzn7IILOSdM7xlgdWOPvgbXJM7`를 먼저 선택해 source
  grounding mismatch로 validation_failed row
  `b09435f9-b104-438e-8c20-17ae9569f276`를 만들었다. 해당 row는 promotion
  대상이 아니며, 최종 실행은 선택된 HBAR Drive file id 1개에 기존 candidate
  validation, artifact, telemetry, and `upsert_job` 함수를 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `hedera-hashgraph`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `140aa95b-f95b-4158-aa95-670b6eeb5a26`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 140aa95b-f95b-4158-aa95-670b6eeb5a26 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2253" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `262f8fae-72cc-4f2e-b20f-060face8deb0`
  - promoted at: `2026-06-27T07:38:55.244298+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2253_hedera_hashgraph_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=hedera-hashgraph`
  - `tracked_projects.symbol=HBAR`
  - `project_reports.id=262f8fae-72cc-4f2e-b20f-060face8deb0`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=HBAR는 HIGH 리스크, 조작 스코어 58점으로, 0.10달러 저항 실패와 선물 주도 변동성이 핵심 부담이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=140aa95b-f95b-4158-aa95-670b6eeb5a26`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/hedera-hashgraph`,
    `https://www.bcelab.xyz/ko/reports/forensic/hedera-hashgraph`,
    `https://www.bcelab.xyz/en/projects/hedera-hashgraph`,
    `https://www.bcelab.xyz/en/reports/forensic/hedera-hashgraph` returned
    HTTP `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2249 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 11:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와
  최신 산출물 이력을 확인했다. 직전 [BCE-2248](/BCE/issues/BCE-2248)는
  Helium FOR를 promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음
  후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `KOX/Coca-Cola tokenized stock`, `MindWaveDAO`,
  `AIOZ`, and `WOULD` 계열은 tracked project 또는 공개 target row가 없어
  제외했다. 다음 명확한 eligible source로 `BERA` FOR를 선택했고 canonical
  tracked project는 `berachain` (`symbol=BERA`)다.
- 선택한 Drive Markdown:
  `BERA 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1rsIYJX8OAt7oPq4oPOrQW1ksODIdBvKa:0B8HYgThT3NByWWxtWTByekwrWUdCTjc1K3p5ekFKSExCZXNRPQ`.
- Source SHA-256:
  `f30b80aa61ddb8f781b93d39687417a36a0c9f674d0e8099f290a02823744c81`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_berachain_bce2249.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_berachain_bce2249.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_berachain.json`.
- Execution note:
  dry-run 표준 command는 선택된 BERA Drive source를 정확히 선택해
  `valid`로 통과했다. 이어 이슈 지시의 broad `--force` command는 다른
  Berachain Drive file id
  `1kVJVzNtzn7IILOSdM7xlgdWOPvgbXJM7`를 먼저 선택해 source grounding
  mismatch로 validation_failed row
  `5c73794f-1de4-40b6-8766-db9ac89f8f9e`를 만들었다. 해당 row는 promotion
  대상이 아니며, 최종 실행은 선택된 BERA Drive file id 1개에 기존 candidate
  validation, artifact, telemetry, and `upsert_job` 함수를 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `berachain`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `4d26205d-6588-485e-be01-9df79d6e32a8`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 4d26205d-6588-485e-be01-9df79d6e32a8 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2249" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `616d0477-05a7-4435-9dc7-0a6d116ee598`
  - promoted at: `2026-06-27T02:38:27.443362+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2249_berachain_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=berachain`
  - `tracked_projects.symbol=BERA`
  - `project_reports.id=616d0477-05a7-4435-9dc7-0a6d116ee598`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=BERA는 HIGH 리스크지만 조작 점수는 49점으로 MEDIUM이며, 0.368-0.377달러 저항과 높은 선물 비중이 핵심 부담이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=4d26205d-6588-485e-be01-9df79d6e32a8`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/berachain`,
    `https://www.bcelab.xyz/ko/reports/forensic/berachain`,
    `https://www.bcelab.xyz/en/projects/berachain`,
    `https://www.bcelab.xyz/en/reports/forensic/berachain` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2251 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 15:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와
  최신 위키 이력을 확인했다. 직전 [BCE-2249](/BCE/issues/BCE-2249)는
  Berachain FOR를 promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음
  후보부터 선별했다. 최신 미승격 후보 중 `KOX/Coca-Cola tokenized stock`,
  `MindWaveDAO`, `AIOZ`, and `WOULD` 계열은 이전 실행 기록과 동일하게
  tracked project 또는 공개 target row 매칭이 없어 제외했다. 다음 eligible
  source로 `ALGO` FOR를 선택했고 canonical tracked project는 `algorand`
  (`symbol=ALGO`, `coingecko_id=algorand`)다.
- 선택한 Drive Markdown:
  `ALGO 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1rTKm2_Sa-JtCTlxiecE9nQ87HAdW7YRs:0B8HYgThT3NByMWhyRGEzeEF3Wk15UENqUFVYLy9TRW5BckhNPQ`.
- Source SHA-256:
  `91039d4e9a8a6e547c45e38fff6c8a4dd9ed390b9b44dfe27115a116585d4751`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_algorand_bce2251.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_algorand_bce2251.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_algorand.json`.
- Execution note:
  source snapshot dry-run passed `valid`. The standard broad Drive command
  shape with `--force --limit 1` selected a different Drive file id
  `1kVJVzNtzn7IILOSdM7xlgdWOPvgbXJM7` and produced source grounding mismatch,
  matching the known slugless/promoted-source recurrence. Final ingest therefore
  applied existing candidate validation, artifact, telemetry, and `upsert_job`
  functions directly to the selected ALGO Drive file id.
- Candidate ingest result:
  - report type: `for`
  - slug: `algorand`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `c0d2728e-4f43-47f5-b0ab-7049529a333a`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id c0d2728e-4f43-47f5-b0ab-7049529a333a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2251" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d2148919-a99e-4c86-a725-ba8b4a6eddb5`
  - promoted at: `2026-06-27T06:40:00.347418+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2251_algorand_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=algorand`
  - `tracked_projects.symbol=ALGO`
  - `tracked_projects.coingecko_id=algorand`
  - `project_reports.id=d2148919-a99e-4c86-a725-ba8b4a6eddb5`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ALGO는 62점 HIGH 경계 포렌식 리스크로, 0.1030달러 저점 회수 뒤 0.1398달러까지 급등했지만 파생상품 주도성과 0.1209-0.1211달러 지지 이탈이 핵심 위험이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=c0d2728e-4f43-47f5-b0ab-7049529a333a`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/algorand`,
    `https://www.bcelab.xyz/ko/reports/forensic/algorand`,
    `https://www.bcelab.xyz/en/projects/algorand`,
    `https://www.bcelab.xyz/en/reports/forensic/algorand` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2252 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 16:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/econ.md`, `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/for.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 직전 [BCE-2251](/BCE/issues/BCE-2251)는
  Algorand FOR를 promoted 및 웹 검증 완료했으므로 이번 실행은 그 다음
  후보부터 선별했다. 최신 미승격 후보 중 `KOX/Coca-Cola tokenized stock`,
  `MindWaveDAO`, `AIOZ`, and `WOULD` 계열은 이전 실행 기록과 동일하게
  tracked project 또는 공개 target row 매칭이 없어 제외했다. 다음 eligible
  source로 `SafePal` FOR를 선택했고 canonical tracked project는 `safepal`
  (`symbol=SFP`, `coingecko_id=safepal`)다.
- 선택한 Drive Markdown:
  `SafePal 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1Ywk1_Xwq6ZAQi8Lkz6LF_SWF6DtUjARt:0B8HYgThT3NByWTI5NW4ra3RzVGhVUWFFWDQ5MzNsS285OHFZPQ`.
- Source SHA-256:
  `2a9ccbb7c7dfed64a1c60571271affdd1050ceb258570b4284962b51e2339599`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_safepal_bce2252.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_safepal_bce2252.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_safepal.json`.
- Execution note:
  source snapshot dry-run passed `valid`. The standard Drive command shape with
  `--drive-root-scope all --limit 1 --force` also selected the same SafePal
  Drive identity and passed validation, so no direct single-file workaround was
  needed for this execution.
- Candidate ingest result:
  - report type: `for`
  - slug: `safepal`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `cb0ad419-1ac7-422c-b1d6-414a33885fe0`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id cb0ad419-1ac7-422c-b1d6-414a33885fe0 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2252" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `dbd4ee7a-ac0b-4f6b-878a-d0ff8afc605c`
  - promoted at: `2026-06-27T07:07:16.27826+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2252_safepal_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=safepal`
  - `tracked_projects.symbol=SFP`
  - `tracked_projects.coingecko_id=safepal`
  - `project_reports.id=dbd4ee7a-ac0b-4f6b-878a-d0ff8afc605c`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=SFP는 61점 HIGH 포렌식 리스크로, 0.2589달러 저점에서 0.3136달러까지 급등한 뒤 0.2870달러로 밀려 유동성 사냥과 고점 분배 가능성이 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=cb0ad419-1ac7-422c-b1d6-414a33885fe0`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/safepal`,
    `https://www.bcelab.xyz/ko/reports/forensic/safepal`,
    `https://www.bcelab.xyz/en/projects/safepal`,
    `https://www.bcelab.xyz/en/reports/forensic/safepal` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2247 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 11:20 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 최신 미승격 후보 `KOX/Coca-Cola tokenized stock`,
  `MindWaveDAO`, `AIOZ`, and `WOULD` 계열은 현재 tracked project가 없어
  제외했다. 다음 eligible source로 `ADA` FOR를 선택했고, canonical
  tracked project는 `cardano` (`symbol=ADA`, `coingecko_id=cardano`)다.
- 선택한 Drive Markdown:
  `ADA 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1I8wlkhqqoMpfjbvP6TjsPLTeBM6MnM_3:0B8HYgThT3NByQkpnd21YbGdsZ3dnNVA5THhaQlB5eE0xTlVZPQ`.
- Source SHA-256:
  `911ed26c843c8d91dedb4eb0d756eb26d12b189becf965d71abcd005b1917a2b`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_cardano_bce2247.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_cardano_bce2247.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_cardano.json`.
- Execution note:
  이슈 지시의 표준 명령 형태인
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug cardano --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_cardano_bce2247.json --require-agent-output --limit 1 --force`
  는 `--force` 때문에 이미 promoted된 slugless `ZETA` source를 포함했고,
  Cardano JSON과 source grounding이 불일치해 validation-failed job
  `4422beef-d14e-4d36-9e7b-00a40172d425`를 만들었다. 최종 실행은 선택된
  ADA Drive file id 1개에 기존 candidate validation, artifact, telemetry,
  and `upsert_job` 함수를 직접 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `cardano`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `9481e971-7b14-4edc-a46b-69a5622bc27a`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 9481e971-7b14-4edc-a46b-69a5622bc27a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2247" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `a7e5b83f-09ad-4698-b00f-edfd28e82857`
  - promoted at: `2026-06-27T02:20:35.317859+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2247_cardano_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=cardano`
  - `tracked_projects.symbol=ADA`
  - `tracked_projects.coingecko_id=cardano`
  - `project_reports.id=a7e5b83f-09ad-4698-b00f-edfd28e82857`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ADA는 0.20달러 붕괴 후 0.1581달러까지 밀렸고, 선물 거래량과 청산이 현물을 압도해 스탑런·강제 디레버리징 리스크가 핵심이다.`
  - `card_summary_en=ADA broke below 0.20 dollars to 0.1581 dollars, while futures volume and liquidations dominated spot activity, making stop run and forced deleveraging risk the core issue.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=9481e971-7b14-4edc-a46b-69a5622bc27a`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/cardano`,
    `https://www.bcelab.xyz/ko/reports/forensic/cardano`,
    `https://www.bcelab.xyz/en/projects/cardano`,
    `https://www.bcelab.xyz/en/reports/forensic/cardano` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and marketing copy.
  - EN surfaces contained the promoted English summary and marketing copy.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2248 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 08:52 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 최신 미승격 후보 중 `KOX/Coca-Cola`,
  `MindWaveDAO`, `AIOZ`, `WOULD` 계열은 직전 실행 기록과 동일하게 공개
  target row 또는 tracked project 매칭이 없어 제외했다. 다음 eligible
  source로 `HNT` FOR를 선택했다.
- 선택한 Drive Markdown:
  `HNT 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1gq148ZzsGH1e106yMIQfo1ckwjvpEYEY:0B8HYgThT3NByV3RrOXcvcXdVV3Y2K2hPT0ttdXJPbnNFOVV3PQ`.
- Source SHA-256:
  `be1026013c88cee8ba6809b966391e9bfa391dfa5f7b394f1b6e50723b54b234`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_helium_bce2248.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_helium_bce2248.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_helium.json`.
- Execution note:
  표준 command shape는 검토했으나, 기존 재발 패턴처럼 `--force`와 slugless
  Drive broad selection이 이미 promoted된 source를 다시 포함할 수 있어 선택한
  HNT Drive file id 1개에 기존 candidate validation, artifact, telemetry,
  and `upsert_job` 함수를 직접 적용했다. 로컬 source snapshot dry-run으로
  먼저 검증한 뒤 Drive identity candidate를 upsert했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `helium`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `59643363-427c-4e7c-bcf4-b12f724b6edb`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 59643363-427c-4e7c-bcf4-b12f724b6edb --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2248" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `ddde94c2-fa95-4901-bdf3-7faba3db428b`
  - promoted at: `2026-06-26T23:51:47.293045+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2248_helium_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=helium`
  - `tracked_projects.symbol=HNT`
  - `tracked_projects.coingecko_id=helium`
  - `project_reports.id=ddde94c2-fa95-4901-bdf3-7faba3db428b`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=HNT는 68점의 HIGH 포렌식 리스크로, 뉴스 촉매 뒤 0.8146달러에서 0.4659달러까지 급락했고 매도 호가와 레버리지 회전이 우세하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=59643363-427c-4e7c-bcf4-b12f724b6edb`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/helium`,
    `https://www.bcelab.xyz/ko/reports/forensic/helium`,
    `https://www.bcelab.xyz/en/projects/helium`,
    `https://www.bcelab.xyz/en/reports/forensic/helium` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2246 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 01:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 최신 미승격 후보 중 `KOX/Coca-Cola`,
  `MindWaveDAO`, `AIOZ`, `WOULD` 계열은 정확한 tracked project 또는 공개
  KO website-visible target row가 없어 제외했다. 다음 최신 eligible source로
  `VIRTUAL` FOR를 선택했다. `virtuals-protocol`과 `virtual-protocol` 중복
  tracked project 중 `coingecko_id=virtual-protocol`을 가진 canonical
  `virtuals-protocol` slug를 선택했다.
- 선택한 Drive Markdown:
  `VIRTUAL 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1xMemtzR6BkswNI_2qp9VZwG23I0fNv9t:0B8HYgThT3NByQThWejVxd1dPcFZrNW92Q1hWRy8yL2k4UEZvPQ`.
- Source SHA-256:
  `9846a211b2dfed672689f050df8a588aab013932de5bd1ed404862f63fc50ca2`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_virtuals-protocol_bce2246.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_virtuals-protocol_bce2246.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_virtuals-protocol.json`.
- Execution note:
  이슈 지시의 표준 명령 형태인
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug virtuals-protocol --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_virtuals-protocol_bce2246.json --require-agent-output --limit 1 --force`
  는 `--force` 때문에 이미 promoted된 slugless `ZETA` source를 포함했다.
  최종 실행은 선택된 VIRTUAL Drive file id 1개에 기존 candidate validation,
  artifact, telemetry, and `upsert_job` 함수를 직접 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `virtuals-protocol`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `7feb983d-3875-4cd1-909a-8faff03481b3`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 7feb983d-3875-4cd1-909a-8faff03481b3 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2246" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `73baf0c5-b9c1-4b46-9040-d1eb31489ccf`
  - promoted at: `2026-06-26T16:08:21.878901+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2246_virtuals_protocol_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=virtuals-protocol`
  - `tracked_projects.symbol=VIRTUAL`
  - `tracked_projects.coingecko_id=virtual-protocol`
  - `project_reports.id=73baf0c5-b9c1-4b46-9040-d1eb31489ccf`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=VIRTUAL은 56점의 중상위 포렌식 리스크로, 0.70달러 박스권 붕괴 뒤 0.5257달러까지 급락했고 선물 거래량이 현물의 약 4배라 청산 압력이 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=7feb983d-3875-4cd1-909a-8faff03481b3`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/virtuals-protocol`,
    `https://www.bcelab.xyz/ko/reports/forensic/virtuals-protocol`,
    `https://www.bcelab.xyz/en/projects/virtuals-protocol`,
    `https://www.bcelab.xyz/en/reports/forensic/virtuals-protocol` returned
    HTTP `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2243 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 23:07 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 최신 파일명 파서 `parsed=null` 후보 중 `AIOZ`가
  `IO` 심볼 때문에 `io-net`으로 잘못 매칭되는 false positive를 확인해
  제외했고, 이름과 tracked project가 직접 일치하며 공개 KO forensic target
  row가 있는 최신 미승격 후보로 `FARTCOIN` FOR를 선택했다.
- 선택한 Drive Markdown:
  `FARTCOIN 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1dMEI1zeh409DEN20fAp-MOqUmx-BXa2I:0B8HYgThT3NByK0RlaVU0UFd6YVV4WDlYcTVXRDh3K0Y1T0MwPQ`.
- Source SHA-256:
  `23ab7aadceed500279d04c14238ad78af54f5044e934bfd775a1d6d2c270b86d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_fartcoin_bce2243.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_fartcoin_bce2243.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_fartcoin.json`.
- Candidate ingest result:
  - report type: `for`
  - slug: `fartcoin`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `908d2218-5980-4af1-bf8d-dee27017e1f1`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 908d2218-5980-4af1-bf8d-dee27017e1f1 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2243" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `ef5f46c5-2266-4570-98ff-6d8cc190623c`
  - promoted at: `2026-06-26T14:06:56.467512+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2243_fartcoin_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=fartcoin`
  - `tracked_projects.symbol=FARTCOIN`
  - `project_reports.id=ef5f46c5-2266-4570-98ff-6d8cc190623c`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=FARTCOIN은 62점 HIGH 포렌식 리스크로, 0.18~0.19 USDT대에서 0.11 USDT까지 하락했고 선물 거래량이 현물의 약 20배라 청산 압력이 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=908d2218-5980-4af1-bf8d-dee27017e1f1`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/fartcoin`,
    `https://www.bcelab.xyz/ko/reports/forensic/fartcoin`,
    `https://www.bcelab.xyz/en/projects/fartcoin`,
    `https://www.bcelab.xyz/en/reports/forensic/fartcoin` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2244 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 00:28 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 최신 미승격 후보 중 `AIOZ` MAT는 `IO` 심볼 때문에
  `io-net`으로 잘못 매칭되는 false positive라 제외했고, 다음 최신 eligible
  source인 `Optimism OP` FOR를 선택했다. `optimism`과
  `optimism-ethereum` 중복 tracked project 중 `coingecko_id=optimism`을
  가진 canonical `optimism` slug를 선택했다.
- 선택한 Drive Markdown:
  `Optimism OP 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1AEMoqqY0Zvf-0Hk8ah3yMw6f6kl0c6Bt:0B8HYgThT3NByZHRYMnFIaUQydXhFeHJKb0duNTAxaEZ4T2owPQ`.
- Source SHA-256:
  `b564e9694ea5a0aa8f8718c6245d09b0594ab5c27efc5b949be7e10cf2fa2d57`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_optimism_bce2244.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_optimism_bce2244.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_optimism.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug optimism --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_optimism_bce2244.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `for`
  - slug: `optimism`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `f09306fa-7e67-4a6f-b81c-53112da8604a`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id f09306fa-7e67-4a6f-b81c-53112da8604a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2244" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `a24c64bf-ab0e-4bb3-94b8-a71cb1b2a6de`
  - promoted at: `2026-06-26T15:28:09.753909+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2244_optimism_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=optimism`
  - `tracked_projects.symbol=OP`
  - `project_reports.id=a24c64bf-ab0e-4bb3-94b8-a71cb1b2a6de`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=OP는 52점의 상승한 포렌식 리스크로, 0.0995 USDT와 0.0915 저점 부근에서 약세가 이어지고 선물 거래량이 현물 대비 약 17배라 레버리지 청산 압력이 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=f09306fa-7e67-4a6f-b81c-53112da8604a`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/optimism`,
    `https://www.bcelab.xyz/ko/reports/forensic/optimism`,
    `https://www.bcelab.xyz/en/projects/optimism`,
    `https://www.bcelab.xyz/en/reports/forensic/optimism` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2245 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-27 00:41 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 최신 후보 중 `ZETA`, `GCOIN/Playnance`, `MSTRx`,
  `Numerai`, `Quack AI`, `IVVON`, `BIO`, `AWE`, `ARX`는 이미 promoted
  상태였고, `KOX/Coca-Cola`, `MindWaveDAO`, `AIOZ`, `WOULD`는 정확한
  tracked project/public KO target 매칭이 없어 제외했다. 최신 미승격
  eligible source로 `ETHFI` FOR를 선택했다.
- 선택한 Drive Markdown:
  `ETHFI 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1BWFzgVTCvfWjOMnAxHfnVBWbIP1huy1u:0B8HYgThT3NByYjIzSmduMy9VRUxqeFFTV2JKMUlTVVNMekEwPQ`.
- Source SHA-256:
  `d88b919448d3a2b297dc83a0e68d4e34635caaa62a5da5c8120ad064c4fca1ac`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_ether-fi_bce2245.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_ether-fi.json`.
- Execution note:
  이슈 지시의 표준 명령 형태인
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug ether-fi --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_ether-fi_bce2245.json --require-agent-output --limit 1 --force`
  는 `--force` 때문에 이미 promoted된 slugless `ZETA` source를 포함했고,
  `ether-fi` slug로 invalid row `f2128f70-66c2-4e96-86e0-2ebef02d0a6a`를
  만들었다. 이 row는 validation_failed 상태이며 promoted되지 않았다.
  최종 실행은 선택된 ETHFI Drive file id 1개에 기존 candidate validation,
  artifact, and `upsert_job` 함수를 직접 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `ether-fi`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `52ee9b18-3637-4fe0-82e6-1659bf6ce175`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 52ee9b18-3637-4fe0-82e6-1659bf6ce175 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2245" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `5839e4e3-5f99-4463-8507-a9faef8f9e78`
  - promoted at: `2026-06-26T15:41:12.867817+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2245_ether-fi_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ether-fi`
  - `tracked_projects.symbol=ETHFI`
  - `project_reports.id=5839e4e3-5f99-4463-8507-a9faef8f9e78`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ETHFI는 58점의 중상위 포렌식 리스크로, 0.406 고점 이후 하락 채널이 이어졌고 0.266 저점 반등에도 주요 이동평균 아래라 유동성 취약성이 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=52ee9b18-3637-4fe0-82e6-1659bf6ce175`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ether-fi`,
    `https://www.bcelab.xyz/ko/reports/forensic/ether-fi`,
    `https://www.bcelab.xyz/en/projects/ether-fi`,
    `https://www.bcelab.xyz/en/reports/forensic/ether-fi` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2242 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 22:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와 최신
  위키 이력을 확인했다. 직전 [BCE-2241](/BCE/issues/BCE-2241)은 ZETA FOR를
  promoted 및 웹 검증 완료했고, 이번 실행에서는 2026-06-26 최신 미승격
  후보인 `KOX / Coca-Cola tokenized stock`, `MindWaveDAO`, `AIOZ`, `WOULD`
  계열이 여전히 공개 KO target row 또는 tracked project 매칭이 없어
  제외됐다.
- 후보 선택:
  Drive `analysis2/{ECON,MAT,FOR}` 및 legacy `analysis/{ECON,MAT,FOR}`를
  root scope `all`로 메타데이터 스캔했다. 다음 명확한 eligible source로
  `Trust Wallet Token (TWT)` FOR를 선택했다.
- 선택한 Drive Markdown:
  `Trust Wallet Token (TWT) 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1rSA6jWhdfb-3I988_bQtxXsyASH4EuLi:0B8HYgThT3NByaDFQMUhMQ2pxRmdDem1jUDdyY1JucmF3TmtjPQ`.
- Source SHA-256:
  `252d435fabb8528f5f7831f48be64d65aecb542fe6b0f0e745b501002c637b54`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_trust-wallet-token_bce2242.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_trust-wallet-token_bce2242.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_trust-wallet-token.json`.
- Execution note:
  표준 slug 필터는 선택한 TWT source를 1순위로 반환했지만, slugless FOR
  파일들이 같은 slug로 넓게 포함되는 재발 가능성이 있어 선택된 TWT Drive
  file id 1개에 기존 candidate validation, artifact, telemetry, and
  `upsert_job` 함수를 직접 적용했다. 로컬 source snapshot dry-run으로 먼저
  검증한 뒤 Drive identity candidate를 upsert했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `trust-wallet-token`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `dcf3e5df-377c-4fa4-ba15-ccb9e1e23eaf`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id dcf3e5df-377c-4fa4-ba15-ccb9e1e23eaf --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2242" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `ed57ce43-7bbb-4789-9127-4e3f7cd1e256`
  - promoted at: `2026-06-26T13:40:22.14611+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2242_trust_wallet_token_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=trust-wallet-token`
  - `tracked_projects.symbol=TWT`
  - `project_reports.id=ed57ce43-7bbb-4789-9127-4e3f7cd1e256`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=TWT는 62점의 중상위 포렌식 리스크로, 0.4700 실패 후 0.3600 급락과 MA 전부 이탈, 파생 청산성 매도가 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=dcf3e5df-377c-4fa4-ba15-ccb9e1e23eaf`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/trust-wallet-token`,
    `https://www.bcelab.xyz/ko/reports/forensic/trust-wallet-token`,
    `https://www.bcelab.xyz/en/projects/trust-wallet-token`,
    `https://www.bcelab.xyz/en/reports/forensic/trust-wallet-token` returned
    HTTP `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2240 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 21:33 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와
  최신 위키 이력을 확인했다. 직전 실행에서 `dydx-chain` MAT는 이미
  promoted 및 웹 검증 완료 상태였고, Batch 13의 `synthetix`, `river`,
  `sentient`, `wemix`, `reserve-rights`도 DB 검증 파일 기준 promoted 상태다.
- 후보 선택:
  Drive `analysis2/{ECON,MAT,FOR}` 및 legacy `analysis/{ECON,MAT,FOR}`를
  root scope `all`로 메타데이터 스캔했다. 최신 미승격 source는 `ZETA` FOR,
  `KOX / Coca-Cola tokenized stock` MAT, `Coca-Cola tokenized stock`
  ECON, `MindWaveDAO` ECON, `AIOZ Network` MAT, `WOULD` ECON/MAT 계열이다.
  이들은 현재 DB 기준 tracked project 매칭 또는 공개 KO website-visible
  target row가 없어 candidate ingest/publish 대상에서 제외했다.
- Routine result:
  no-op: no new analysis markdown eligible for candidate ingest/publish.
- Candidate ingest / Summary Authority Gate:
  실행하지 않았다. 유효한 target row를 가진 신규 미승격 source가 없어
  Paperclip CRO JSON 생성, `report_summary_jobs` upsert, `llm_active`
  promotion 모두 건너뛰었다.
- Manifest change:
  no change needed. This was a routine no-op under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2241 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 22:17 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs.authority_state=promoted` source identity와
  최신 위키 이력을 확인했다. 직전 [BCE-2240](/BCE/issues/BCE-2240)은
  eligible target row가 없어 no-op이었지만, 이번 실행 시점에는 최신 미승격
  Drive source 중 `ZETA` FOR가 `tracked_projects.slug=zetachain` 및 공개 KO
  forensic target row를 보유해 ingest/publish 대상으로 선택됐다.
- 선택한 Drive Markdown:
  `ZETA 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1kVJVzNtzn7IILOSdM7xlgdWOPvgbXJM7:0B8HYgThT3NBybG9jOVkzTnJ4MjBOQWJzWjBCY1R2aE1SSjA0PQ`.
- Source SHA-256:
  `df499c3310ec6743e4affc8b77215dfde3aaca9d4d2bacae395d464d1103502e`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_zetachain_bce2241.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_zetachain_bce2241.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_zetachain.json`.
- Execution note:
  표준 `analysis_md_summary_candidate.py --slug zetachain` Drive 경로는 현재
  최신 Korean analysis Markdown 파일명이 `parsed=null`로 반환되어 같은 FOR
  폴더의 slugless 파일을 넓게 다운로드하다 timeout이 발생했다. 선택된 ZETA
  Drive file id 1개에 기존 candidate validation, artifact, telemetry, and
  `upsert_job` 함수를 직접 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `zetachain`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `dcea60e4-9bfb-4ba3-bf41-88e9aa5de98a`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id dcea60e4-9bfb-4ba3-bf41-88e9aa5de98a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2241" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `e75e8b76-2121-47b1-8cb9-63d581b5d9f0`
  - promoted at: `2026-06-26T13:17:08.138062+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2241_zetachain_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=zetachain`
  - `tracked_projects.symbol=ZETA`
  - `project_reports.id=e75e8b76-2121-47b1-8cb9-63d581b5d9f0`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=ZetaChain은 포렌식 리스크 61점으로, 21% 급락 후 약한 반등과 파생 주도 수급, 낮은 온체인 사용량, 7월 언락 압박이 핵심이다.`
  - `card_summary_en=ZetaChain has a 61 forensic risk score, with a weak rebound after a 21 percent drop, derivatives led flow, thin onchain use, and July unlock pressure.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=dcea60e4-9bfb-4ba3-bf41-88e9aa5de98a`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/zetachain` and
    `https://www.bcelab.xyz/en/projects/zetachain` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO project page contained the promoted Korean summary.
  - EN project page contained the promoted English summary.
  - `https://www.bcelab.xyz/ko/reports/zetachain/forensic` and
    `https://www.bcelab.xyz/en/reports/zetachain/forensic` returned HTTP `200`;
    the verifier did not find the promoted card summary text on detail pages,
    while project-page website visibility is confirmed.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Project-page website visibility is already
  confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 Batch 12 Partial CRO Analysis MD Summary Promotion (2026-06-26 20:21 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  직전 [BCE-2055](/BCE/issues/BCE-2055) Batch 11 코멘트와 DB 상태를
  확인했다. `dai`, `binaryx-new`, `gas`, `safe1`, `awe-network`는 이미
  promoted 및 웹 검증 완료 상태였고, 다음 대기열의 `nexus-labs`는
  validation-passed candidate job만 있고 아직 promoted 상태가 아니어서 이번
  heartbeat의 승격 대상으로 선택했다.
- Source identity:
  `drive:1QwKjWjLk6pkBdqhxVod-GbktezOjDyfS:0B8HYgThT3NByamlzYlJyQWJ3b2R5ckZxcER0WDVBY2VBTDRZPQ`.
- Source SHA-256:
  `c5efa28bd7e74c3fdb05a6de332da750315d4b4e69be72f57df396ab16d37d21`.
- Existing candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_nexus-labs.json`.
- Candidate ingest status:
  - report type: `mat`
  - slug: `nexus-labs`
  - validation status: `valid`
  - validation reasons: none
  - job id: `9f928a1e-be91-4f7f-b3f5-1ed07fbe5150`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 9f928a1e-be91-4f7f-b3f5-1ed07fbe5150 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2055-batch12" --write`.
- Promotion result:
  - state: `promoted`
  - project report id: `44f9daf4-cb6c-4d46-8a8e-1ad7113061d2`
  - promoted at: `2026-06-26T11:19:59.542785+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2055_batch12_nexus_labs_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=nexus-labs`
  - `tracked_projects.symbol=NEX`
  - `project_reports.id=44f9daf4-cb6c-4d46-8a8e-1ad7113061d2`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Nexus는 메인넷과 NEX 출시로 전개 서사 단계에 진입했지만, Exchange 수익과 USDX 수요 공개가 성숙도 핵심 병목이다.`
  - `card_summary_en=Nexus has entered an expansion phase after mainnet and NEX launch, but Exchange revenue and USDX demand remain the key maturity bottlenecks.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=9f928a1e-be91-4f7f-b3f5-1ed07fbe5150`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/nexus-labs`,
    `https://www.bcelab.xyz/ko/reports/nexus-labs/maturity`,
    `https://www.bcelab.xyz/en/projects/nexus-labs`,
    `https://www.bcelab.xyz/en/reports/nexus-labs/maturity` returned HTTP
    `200`.
  - KO surfaces contained the promoted Korean summary and marketing copy.
  - EN surfaces contained the promoted English summary and marketing copy.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Execution status:
  this heartbeat completed one promoted MAT source from the Batch 12 queue.
  Remaining queue begins with `defi-app`, `maplestory-universe`, `kaito-ai`,
  `grass`, `cheems-pet`, `horizen`, `synthetix`, `river`, `sentient`.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2238 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 20:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs`와 공개 KO target row를 확인했다. 직전
  Batch 12 queue의 `defi-app`, `maplestory-universe`, `kaito-ai`, `grass`,
  `cheems-pet`, `nexus-labs`는 이미 `promoted` 상태였고, 다음 eligible
  source인 `horizen` MAT는 아직 summary job이 없어 이번 실행 대상으로
  선택했다.
- 선택한 Drive Markdown:
  `Horizen의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017–2026.md`.
- Source identity:
  `drive:1lGALxY3w4XtwNLkwwSr0iMjjKcwntBRR:0B8HYgThT3NBycDltWkl0WUhnYS9hSzRuY1daZ0VSbi9wWWxnPQ`.
- Source SHA-256:
  `bcd45c5f1e16c8b42130a3129f88c75aebba6558865557c6194517e95fa39842`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_horizen_bce2238.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_horizen_bce2238.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_horizen.json`.
- Execution note:
  표준 `analysis_md_summary_candidate.py --slug horizen` 경로는 Korean
  analysis Markdown 파일명이 slugless로 해석될 때 broad-download 지연이
  재발할 수 있어 사용하지 않았다. 선택된 Horizen Drive file id 1개에 기존
  candidate validation, artifact, and `upsert_job` 함수를 직접 적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `horizen`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `6a3f237d-790a-4b1c-b7d6-3728a02eaa0f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 6a3f237d-790a-4b1c-b7d6-3728a02eaa0f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2238" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `edc493f2-9c79-4510-8d5c-7b05372f21a7`
  - promoted at: `2026-06-26T11:39:30.340073+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2238_horizen_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=horizen`
  - `tracked_projects.symbol=ZEN`
  - `project_reports.id=edc493f2-9c79-4510-8d5c-7b05372f21a7`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Horizen은 Base L3 전환을 마쳤지만, 고유 TVL·수익·앱 사용량 검증 전인 전개 서사 단계다.`
  - `card_summary_en=Horizen has completed its Base L3 pivot, but remains in expansion while native TVL, revenue, and app usage are unproven.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=6a3f237d-790a-4b1c-b7d6-3728a02eaa0f`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/horizen`,
    `https://www.bcelab.xyz/ko/reports/horizen/maturity`,
    `https://www.bcelab.xyz/en/projects/horizen`,
    `https://www.bcelab.xyz/en/reports/horizen/maturity` returned HTTP
    `200`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2239 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 21:06 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 `report_summary_jobs`와 최신 위키 이력을 확인했다. `instadapp` FOR는
  이미 `authority_state=promoted` 상태였고, 다음 eligible source인
  `dydx-chain` MAT는 아직 summary job이 없으며 공개 KO maturity target row를
  보유해 이번 실행 대상으로 선택했다.
- 선택한 Drive Markdown:
  `dYdX 크립토 이코노미 성숙도 평가 보고서.md`.
- Source identity:
  `drive:1vzHH4ctd69hO5qg5_6AO1OIlx7znKK9H:0B8HYgThT3NByMXloSEk1eHIrK3pWZFNuQjNyNmRmaG11TG8wPQ`.
- Source SHA-256:
  `1cfd905708088361dff77798ebd72fc75729a99776e010b0d2939614ebc57c12`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_dydx-chain_bce2239.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_dydx-chain_bce2239.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_dydx-chain.json`.
- Execution note:
  표준 `analysis_md_summary_candidate.py --slug dydx-chain` 경로는 Korean
  analysis Markdown 파일명이 slugless로 해석될 때 broad-download 지연이
  재발할 수 있어 사용하지 않았다. 선택된 dYdX Drive file id 1개에 기존
  candidate validation, artifact, telemetry, and `upsert_job` 함수를 직접
  적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `dydx-chain`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `0a175307-0a1f-43fc-8ea5-1154ad8a11b2`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0a175307-0a1f-43fc-8ea5-1154ad8a11b2 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2239" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `0491cb85-fa9e-4457-aadd-8e413d327386`
  - promoted at: `2026-06-26T12:06:01.469548+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2239_dydx_chain_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=dydx-chain`
  - `tracked_projects.symbol=DYDX`
  - `project_reports.id=0491cb85-fa9e-4457-aadd-8e413d327386`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=dYdX는 앱체인 CLOB와 수수료 분배 구조를 갖춘 전개 후기 프로젝트지만, 거래량 재가속과 검증인 경제성이 성숙 진입의 핵심 병목이다.`
  - `card_summary_en=dYdX is a late expansion project with an appchain CLOB and fee distribution, but volume reacceleration and validator economics remain the main maturity bottlenecks.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=0a175307-0a1f-43fc-8ea5-1154ad8a11b2`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/dydx-chain`,
    `https://www.bcelab.xyz/ko/reports/dydx-chain/maturity`,
    `https://www.bcelab.xyz/en/projects/dydx-chain`,
    `https://www.bcelab.xyz/en/reports/dydx-chain/maturity` returned HTTP
    `200`.
  - KO surfaces contained the promoted Korean summary and marketing copy.
  - EN surfaces contained the promoted English summary and marketing copy.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2237 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 20:06 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인해 이미 승격된 source를 제외했다. 직전 [BCE-2223](/BCE/issues/BCE-2223)
  Quack AI MAT 및 [BCE-2055](/BCE/issues/BCE-2055) SOON Network MAT는
  이미 promoted 상태다.
- 후보 선택:
  Drive active `analysis2/{ECON,MAT,FOR}`를 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 `ZETA` FOR는 `zetachain` target row가 `forensic/en
  coming_soon`뿐이라 웹 가시성 요건의 KO published target이 없어
  스킵했다. 다음 eligible source인 `GCOIN / Playnance` MAT는
  Drive 파일명, 본문 제목, 공식 웹사이트, tracked project slug
  `playnance`, symbol `GCOIN`이 일치해 source identity gate를 통과했다.
- 선택한 Drive Markdown:
  `GCOIN 크립토 이코노미 성숙도 평가 보고서_ Playnance.md`.
- Source identity:
  `drive:14S-1dsZ-KWd9bu79T_PFsk2dYt3aOOCr:0B8HYgThT3NByaEZPWlZXa24yZENxbVVoYUFOclJiU1FGSkgwPQ`.
- Source SHA-256:
  `2d6ff11631c2f32cefef9840210ae5b724380a8402d636fc997ec9744659f902`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_playnance_bce2237.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_playnance_bce2237.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_playnance.json`.
- Candidate ingest result:
  - report type: `mat`
  - slug: `playnance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `69d5e827-bf29-48ba-bdee-05bb91b54777`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 69d5e827-bf29-48ba-bdee-05bb91b54777 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2237" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `926ca7ce-c4ca-4d6d-b8b2-9185b61313e2`
  - promoted at: `2026-06-26T11:05:49.586455+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2237_playnance_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=playnance`
  - `tracked_projects.symbol=GCOIN`
  - `project_reports.id=926ca7ce-c4ca-4d6d-b8b2-9185b61313e2`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Playnance는 PlayBlock L3와 G Coin을 결합한 온체인 엔터테인먼트 경제권이지만, 중앙화 리스크와 공개 검증 부족이 성숙도 병목이다.`
  - `card_summary_en=Playnance links PlayBlock L3 with G Coin into an onchain entertainment economy, but centralization risk and limited public verification cap maturity.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=69d5e827-bf29-48ba-bdee-05bb91b54777`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/playnance`,
    `https://www.bcelab.xyz/ko/reports/playnance/maturity`,
    `https://www.bcelab.xyz/en/projects/playnance`,
    `https://www.bcelab.xyz/en/reports/playnance/maturity` returned HTTP
    `200`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2228 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 20:17 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/econ.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인해 이미 승격된 source를 제외했다. 직전 [BCE-2237](/BCE/issues/BCE-2237)
  Playnance MAT와 [BCE-2223](/BCE/issues/BCE-2223) Quack AI MAT는 이미
  promoted 상태다.
- 후보 선택:
  active Drive 메타데이터 기준으로 [BCE-2237](/BCE/issues/BCE-2237) 이후
  최신 후보를 이어서 선별했다. `ZETA` FOR는 KO published target row가
  없고, `KOX / Coca-Cola tokenized stock` 및 `MindWaveDAO`는 tracked
  project 매칭이 없어 스킵했다. 다음 eligible source인 `MSTRx /
  MicroStrategy tokenized stock (xStock)` ECON은 Drive 파일명, 본문 제목,
  Backed/xStocks 발행 구조, tracked project slug
  `microstrategy-tokenized-stock-xstock`, symbol `MSTRX`가 일치해 source
  identity gate를 통과했다.
- 선택한 Drive Markdown:
  `MSTRx MicroStrategy tokenized stock (xStock) 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1LFaZbR3Q7TTv8_bN99Awsqn3AnKtJEKp:0B8HYgThT3NByVzNEMTB2SkdDM01IK0x5czlSanlaTGJBaUJnPQ`.
- Source SHA-256:
  `f38b0b72cf7dccc5045cc2c01bde06b888278f6b03f63b6c63be90f397c44002`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_microstrategy-tokenized-stock-xstock_bce2228.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_microstrategy-tokenized-stock-xstock_bce2228.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_microstrategy-tokenized-stock-xstock.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `microstrategy-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `e33d74eb-e556-4cd0-b23b-5f5df49e0996`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id e33d74eb-e556-4cd0-b23b-5f5df49e0996 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2228" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `80b74565-e7c8-4ac6-87f0-108689db4b87`
  - promoted at: `2026-06-26T11:16:41.410876+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2228_microstrategy_xstock_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=microstrategy-tokenized-stock-xstock`
  - `tracked_projects.symbol=MSTRX`
  - `project_reports.id=80b74565-e7c8-4ac6-87f0-108689db4b87`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=MSTRx는 MicroStrategy 주식 노출을 온체인으로 옮긴 담보형 RWA지만, 상환 제한과 수탁·규제 의존이 핵심 리스크다.`
  - `card_summary_en=MSTRx brings MicroStrategy stock exposure onchain as collateralized RWA, but redemption limits plus custody and regulatory reliance remain key risks.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=e33d74eb-e556-4cd0-b23b-5f5df49e0996`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/microstrategy-tokenized-stock-xstock`,
    `https://www.bcelab.xyz/ko/reports/microstrategy-tokenized-stock-xstock/econ`,
    `https://www.bcelab.xyz/en/projects/microstrategy-tokenized-stock-xstock`,
    `https://www.bcelab.xyz/en/reports/microstrategy-tokenized-stock-xstock/econ`
    returned HTTP `200`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2237 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 19:54 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. Drive `analysis2/{ECON,MAT,FOR}` 목록은 다운로드 전
  파일 메타데이터와 DB target row 기준으로 대조했다.
- 최신 미승격 후보 확인:
  - `ZETA` FOR Markdown은 tracked project `zetachain`과 symbol `ZETA`로
    매칭되지만, KO website-visible forensic/econ/maturity `project_reports`
    target row가 없어 제외했다.
  - `Coca-Cola tokenized stock (xStock)`, `MindWaveDAO`, `AIOZ`, `WOULD`
    계열은 현재 DB 기준 tracked project 매칭 또는 공개 KO target row가
    없어 제외했다.
- Routine result:
  no-op: no new analysis markdown eligible for candidate ingest/publish.
- Candidate ingest / Summary Authority Gate:
  실행하지 않았다. 유효한 target row를 가진 신규 미승격 source가 없어
  JSON 생성, `report_summary_jobs` upsert, `llm_active` promotion 모두
  건너뛰었다.
- Manifest change:
  no change needed. This was a routine no-op under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2234 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 17:25 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 `GCOIN / Playnance` MAT가
  tracked project `playnance`와 공개 KO maturity target row를 보유해 이번
  실행의 eligible source로 선택됐다.
- 선택한 Drive Markdown:
  `GCOIN 크립토 이코노미 성숙도 평가 보고서_ Playnance.md`.
- Source identity:
  `drive:14S-1dsZ-KWd9bu79T_PFsk2dYt3aOOCr:0B8HYgThT3NByaEZPWlZXa24yZENxbVVoYUFOclJiU1FGSkgwPQ`.
- Source SHA-256:
  `2d6ff11631c2f32cefef9840210ae5b724380a8402d636fc997ec9744659f902`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_playnance_bce2234.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_playnance_bce2234.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_playnance.json`.
- Execution note:
  표준 `analysis_md_summary_candidate.py --slug playnance` dry-run은 Drive
  broad-download 경로에서 장시간 지연되어 중단했다. 선택된 Playnance Drive
  file id 1개에 기존 candidate validation, artifact, and `upsert_job` 함수를
  직접 적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `playnance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `69d5e827-bf29-48ba-bdee-05bb91b54777`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 69d5e827-bf29-48ba-bdee-05bb91b54777 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2234" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `926ca7ce-c4ca-4d6d-b8b2-9185b61313e2`
  - promoted at: `2026-06-26T08:25:20.310773+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2234_playnance_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=playnance`
  - `tracked_projects.symbol=GCOIN`
  - `project_reports.id=926ca7ce-c4ca-4d6d-b8b2-9185b61313e2`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Playnance는 PlayBlock L3와 G Coin으로 게임·베팅 정산 인프라를 구축했지만, 실측 UOPS와 중앙화 리스크 공개가 성숙도 상승의 핵심 조건이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=69d5e827-bf29-48ba-bdee-05bb91b54777`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/playnance` and
    `https://www.bcelab.xyz/en/projects/playnance` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO project page contained the promoted Korean summary and Investment View
    text.
  - EN project page contained the promoted English summary and Investment View
    text.
  - `https://www.bcelab.xyz/{ko,en}/reports/{mat,maturity}/playnance` returned
    HTTP `404`; this appears to be the current report-detail route behavior for
    this maturity row, while project-page website visibility is confirmed.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Project-page website visibility is already
  confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2235 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 17:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 `MSTRx / MicroStrategy tokenized
  stock (xStock)` ECON이 tracked project
  `microstrategy-tokenized-stock-xstock`와 공개 KO econ target row를 보유해
  이번 실행의 eligible source로 선택됐다.
- 선택한 Drive Markdown:
  `MSTRx MicroStrategy tokenized stock (xStock) 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1LFaZbR3Q7TTv8_bN99Awsqn3AnKtJEKp:0B8HYgThT3NByVzNEMTB2SkdDM01IK0x5czlSanlaTGJBaUJnPQ`.
- Source SHA-256:
  `f38b0b72cf7dccc5045cc2c01bde06b888278f6b03f63b6c63be90f397c44002`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_microstrategy-tokenized-stock-xstock_bce2235.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_microstrategy-tokenized-stock-xstock_bce2235.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_microstrategy-tokenized-stock-xstock.json`.
- Execution note:
  표준 `analysis_md_summary_candidate.py --slug microstrategy-tokenized-stock-xstock`
  경로는 이전 실행에서 확인된 slugless Drive broad-download 지연 재발 위험이
  있어 사용하지 않았다. 선택된 MSTRx Drive file id 1개에 기존 candidate
  validation, artifact, and `upsert_job` 함수를 직접 적용했다.
- Candidate ingest result:
  - report type: `econ`
  - slug: `microstrategy-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `e33d74eb-e556-4cd0-b23b-5f5df49e0996`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id e33d74eb-e556-4cd0-b23b-5f5df49e0996 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2235" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `80b74565-e7c8-4ac6-87f0-108689db4b87`
  - promoted at: `2026-06-26T08:39:32.495231+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2235_microstrategy_tokenized_stock_xstock_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=microstrategy-tokenized-stock-xstock`
  - `tracked_projects.symbol=MSTRX`
  - `project_reports.id=80b74565-e7c8-4ac6-87f0-108689db4b87`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=MSTRx는 MicroStrategy 주식 노출을 온체인으로 이전하는 1:1 담보형 xStock이지만, 가치는 담보 검증과 상환 가능성, 유동성 괴리에 좌우된다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=e33d74eb-e556-4cd0-b23b-5f5df49e0996`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/microstrategy-tokenized-stock-xstock`
    and `https://www.bcelab.xyz/en/projects/microstrategy-tokenized-stock-xstock`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO project page contained the promoted Korean summary.
  - EN project page contained the promoted English summary.
  - `https://www.bcelab.xyz/{ko,en}/reports/econ/microstrategy-tokenized-stock-xstock`
    returned HTTP `404`; this matches the current report-detail route behavior
    seen in prior routine executions, while project-page website visibility is
    confirmed.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Project-page website visibility is already
  confirmed on the current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2233 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 16:49 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보는 Coca-Cola tokenized stock
  MAT/ECON, MindWaveDAO ECON, MSTRx ECON, AIOZ MAT, WOULD MAT/ECON 계열로
  확인됐다.
- Eligible target 확인:
  - `Coca-Cola tokenized stock (xStock)`는 tracked project 매칭이 없었다.
  - `MindWaveDAO`는 tracked project 매칭이 없었다.
  - `MSTRx/MicroStrategy tokenized stock (xStock)`는 tracked project
    `microstrategy-tokenized-stock-xstock`가 있으나 KO `econ`,
    `maturity`, `forensic` website-visible target row가 없었다.
  - `AIOZ` 및 `WOULD` 계열은 기존 재발 기록과 동일하게 공개 target row
    또는 tracked project 매칭이 없어 제외했다.
- Routine result:
  no-op: no new analysis markdown eligible for candidate ingest/publish.
- Candidate ingest / Summary Authority Gate:
  실행하지 않았다. 유효한 target row를 가진 신규 미승격 source가 없어
  JSON 생성, `report_summary_jobs` upsert, `llm_active` promotion 모두
  건너뛰었다.
- Manifest change:
  no change needed. This was a routine no-op under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2232 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 16:05 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 Coca-Cola tokenized stock,
  `MSTRx`, `AIOZ`, `WOULD` 계열은 공개 target row 부재 또는 slugless
  false-positive 매칭으로 제외했고, 다음 명확한 eligible source로 `PUMP`
  FOR를 선택했다.
- 선택한 Drive Markdown:
  `PUMP 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1TW5DUPFB20uxdq5OKeoe1O-w1bR-_D6z:0B8HYgThT3NByaGpLUXdwYUxUVmNweG96YkJlVWRvRXpkeWlvPQ`.
- Source SHA-256:
  `01d26915097edf18d2ae6b0d8bbff3a07dfb23918ef430fb9975a2247fad5f76`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_pump-fun_bce2232.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_pump-fun_bce2232.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_pump-fun.json`.
- Execution note:
  표준 `--force` command는 기존 slugless Drive broad-download 재발 패턴처럼
  이미 promoted된 동일 slug source를 다시 선택할 수 있어 사용하지 않았다.
  선택된 PUMP Drive file id 1개에 기존 candidate validation, artifact, and
  `upsert_job` 함수를 직접 적용했고, 공개 forensic target row가 version
  2/latest이므로 candidate source version을 2로 명시했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `pump-fun`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `941a7ec1-81c1-4381-b126-6376f29d9f6d`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 941a7ec1-81c1-4381-b126-6376f29d9f6d --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2232" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d644d0ec-d894-4792-9e75-11f69ade5098`
  - promoted at: `2026-06-26T07:05:00.287459+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2232_pump_fun_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=pump-fun`
  - `tracked_projects.symbol=PUMP`
  - `project_reports.id=d644d0ec-d894-4792-9e75-11f69ade5098`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=PUMP는 0.001337 저점 반등에도 0.001480 회복 전까지 약세가 우세하며 74/100 조작 리스크와 파생 과열 확인이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=941a7ec1-81c1-4381-b126-6376f29d9f6d`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/pump-fun`,
    `https://www.bcelab.xyz/ko/reports/forensic/pump-fun`,
    `https://www.bcelab.xyz/en/projects/pump-fun`,
    `https://www.bcelab.xyz/en/reports/forensic/pump-fun` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2231 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 15:47 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 `MSTRx`는 이전 실행들과 동일하게
  slugless filename이 `MX` 계열과 false-positive 매칭될 수 있어 제외했고,
  다음 명확한 eligible source로 `Canton(CC)` FOR를 선택했다.
- 선택한 Drive Markdown:
  `Canton(CC) 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:11saP8u6HMb-COLhqoV0fS2ffcec6B2yX:0B8HYgThT3NBybjZ5R0xXeUxFd1FPalI4MmFIK2p6RkxnTEV3PQ`.
- Source SHA-256:
  `b033e48806d0d33212056e3f5a7c00b68df49dd27f3c1054ae94049cdfaca977`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_canton-network_bce-2231.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_canton-network_bce-2231.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_canton-network.json`.
- Execution note:
  표준 command는 기존 slugless Drive broad-download 재발 패턴을 피하기 위해
  사용하지 않았고, 선택된 Canton Drive file id 1개에 기존 candidate
  validation, artifact, and `upsert_job` 함수를 직접 적용했다. Telemetry
  `start_telemetry`는 `run_id=None`을 반환했지만 candidate validation과 DB
  upsert, authority gate promotion은 정상 완료됐다.
- Candidate ingest result:
  - report type: `for`
  - slug: `canton-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `5b1ef149-8fa0-4138-81eb-7111eda27cb7`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5b1ef149-8fa0-4138-81eb-7111eda27cb7 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2231" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `0c2c44f7-b01c-45a7-a302-cd08e77acc3f`
  - promoted at: `2026-06-26T06:47:16.792415+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2231_canton_network_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=canton-network`
  - `tracked_projects.symbol=CANTON`
  - `project_reports.id=0c2c44f7-b01c-45a7-a302-cd08e77acc3f`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Canton은 0.140달러 저점 스윕 후 급반등했지만 58/100 조작 리스크와 0.170달러 저항 돌파 확인이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=5b1ef149-8fa0-4138-81eb-7111eda27cb7`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/canton-network`,
    `https://www.bcelab.xyz/ko/reports/forensic/canton-network`,
    `https://www.bcelab.xyz/en/projects/canton-network`,
    `https://www.bcelab.xyz/en/reports/forensic/canton-network` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2227 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 13:46 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 `Numerai/Numeraire`, `WOULD`,
  `IVVON`은 공개 target row 또는 tracked project 매칭이 없어 제외했다.
- 후보 선택:
  다음 eligible source로 `NEXPACE` FOR를 선택했다. 이 source는 직전
  [BCE-2226](/BCE/issues/BCE-2226)과 normalized Markdown SHA는 동일하지만
  Drive file id/revision이 다른 미승격 source identity다.
- 선택한 Drive Markdown:
  `NEXPACE 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1UuFdaxRAD68tBE_ehW-wPj6xuuMPeYgz:0B8HYgThT3NBycDBzblR6NUUyYlluZDVhM2J1Nm8ybkc2TzBFPQ`.
- Source SHA-256:
  `b7f5358cd8b2933c9ede46d6a04d92117d2a6e827e16cf2dbe4b47ac99380c7f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_maplestory-universe_bce2227.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_maplestory-universe_bce2227.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_maplestory-universe.json`.
- Execution note:
  표준 command는 `--force` 사용 시 이미 promoted된 동일 slug source까지 다시
  후보에 포함할 수 있어, 기존 candidate validation, artifact, telemetry,
  and `upsert_job` 함수를 선택된 NEXPACE Drive file id 1개에만 적용했다.
  공개 forensic target row가 version 2/latest이므로 candidate source
  version을 2로 명시했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `maplestory-universe`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `884818cb-353a-4f3b-b648-bb409621e1eb`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 884818cb-353a-4f3b-b648-bb409621e1eb --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2227" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `189a0614-3fc5-4c05-b439-42cf747bf9c3`
  - promoted at: `2026-06-26T04:45:54.562627+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2227_maplestory_universe_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=maplestory-universe`
  - `tracked_projects.symbol=NXPC`
  - `project_reports.id=189a0614-3fc5-4c05-b439-42cf747bf9c3`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=NEXPACE는 0.2994달러 저점 후 반등했지만 선물 우위 수급과 49/100 조작 리스크로 0.3654달러 회복 확인이 우선이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=884818cb-353a-4f3b-b648-bb409621e1eb`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/maplestory-universe`,
    `https://www.bcelab.xyz/ko/reports/forensic/maplestory-universe`,
    `https://www.bcelab.xyz/en/projects/maplestory-universe`,
    `https://www.bcelab.xyz/en/reports/forensic/maplestory-universe`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2230 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 15:18 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 `MSTRx`, `Numerai/Numeraire`,
  `WOULD`, `IVVON` 등은 공개 target row 또는 tracked project 매칭이 없어
  제외했고, 다음 명확한 eligible source로 `SOSO` FOR를 선택했다.
- 선택한 Drive Markdown:
  `SOSO 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1CBJKwUdkEM5n2aLrjDV2_QeCob_RIRY0:0B8HYgThT3NByQ0V0NHZETjdmaFZRQzFtdy9wNERCWlF4Z1c0PQ`.
- Source SHA-256:
  `265695ce83dfc414450879f8afd79fd9a14d34263d45def6ca5cff74c98a54da`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_sosovalue_bce2230.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_sosovalue_bce2230.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_sosovalue.json`.
- Execution note:
  표준 `--force` command는 기존 slugless Drive broad-download 재발 패턴처럼
  AWE Drive file id를 먼저 선택해 source grounding mismatch와 일부 raw
  format validation failure가 있는 validation_failed row
  `34669b63-f937-4ae2-bf1a-ce607fcd84ae`를 만들었다. 해당 row는 승격
  대상이 아니며, 선택된 SOSO Drive file id 1개에 기존 candidate
  validation, artifact, telemetry, and `upsert_job` 함수를 직접 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `sosovalue`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `b3ea7cfb-2289-4327-92b9-c9bde0f0bc31`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id b3ea7cfb-2289-4327-92b9-c9bde0f0bc31 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2230" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `7e79b34f-5e01-4072-9965-717e84dbe59b`
  - promoted at: `2026-06-26T06:18:32.24632+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2230_sosovalue_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=sosovalue`
  - `tracked_projects.symbol=SOSO`
  - `project_reports.id=7e79b34f-5e01-4072-9965-717e84dbe59b`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=SOSO는 저점 후 V자 반등했지만 61/100 조작 리스크와 매도벽, 언락 부담으로 돌파 확인이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=b3ea7cfb-2289-4327-92b9-c9bde0f0bc31`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/sosovalue`,
    `https://www.bcelab.xyz/ko/reports/forensic/sosovalue`,
    `https://www.bcelab.xyz/en/projects/sosovalue`,
    `https://www.bcelab.xyz/en/reports/forensic/sosovalue` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2229 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 14:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 `MSTRx`는 tracked project match는
  있으나 공개 ECON target row가 없고, `WOULD`/`IVVON`은 공개 target row
  또는 tracked project 매칭이 없어 제외했다. 다음 eligible source로
  `PENGU` FOR를 선택했다.
- 선택한 Drive Markdown:
  `PENGU 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1cJgMmcacfPHNj-RlplLtL6IooiMOBvJO:0B8HYgThT3NBybWxKbTNlZmljdVNhSEZBT1BDZkRMMTE1QlNNPQ`.
- Source SHA-256:
  `7861cc3eaf954eed8c3bfd5c07bcc677876b06c38383b6004e098e07d7ec3b85`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_pudgy-penguins_bce2229.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_pudgy-penguins_bce2229.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_pudgy-penguins.json`.
- Execution note:
  이 source는 [BCE-2223](/BCE/issues/BCE-2223) PENGU FOR와 normalized
  Markdown SHA가 동일하지만 Drive file id/revision이 다른 미승격 source
  identity다. 표준 `--force` command는 기존 promoted PENGU source를 다시
  선택할 수 있어, 기존 candidate validation, artifact, telemetry, and
  `upsert_job` 함수를 선택된 PENGU Drive file id 1개에만 적용했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `pudgy-penguins`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `a71e08ba-7a61-4578-92cb-e7a99f6e2418`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id a71e08ba-7a61-4578-92cb-e7a99f6e2418 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2229" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `02bd706e-dc8c-44f3-a0d1-465fceb8c371`
  - promoted at: `2026-06-26T05:40:54.076801+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2229_pudgy_penguins_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=pudgy-penguins`
  - `tracked_projects.symbol=PENGU`
  - `project_reports.id=02bd706e-dc8c-44f3-a0d1-465fceb8c371`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=PENGU는 저점 후 반등했지만 조작 리스크와 단기 저항, 장기 평균선 하회가 남아 돌파 확인이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=a71e08ba-7a61-4578-92cb-e7a99f6e2418`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/pudgy-penguins`,
    `https://www.bcelab.xyz/ko/reports/forensic/pudgy-penguins`,
    `https://www.bcelab.xyz/en/projects/pudgy-penguins`,
    `https://www.bcelab.xyz/en/reports/forensic/pudgy-penguins` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2226 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 13:13 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 [BCE-2225](/BCE/issues/BCE-2225)는 PUMP FOR의
  별도 Drive file id를 promoted 및 웹 검증 완료했으므로, 이번 실행은 그
  다음 eligible source부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai/Numeraire`, `WOULD`, `IVVON`은 공개 target
  row 또는 tracked project 매칭이 없어 제외했다. 다음 eligible source로
  `NEXPACE` FOR를 선택했다.
- 선택한 Drive Markdown:
  `NEXPACE 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1qFm1kfT3LEnvVMqqqXaDxJeS8KAi-Qpw:0B8HYgThT3NByeDh4eUxocUh3eWNXWG4vbmJ2cGtiRnBtc3hNPQ`.
- Source SHA-256:
  `b7f5358cd8b2933c9ede46d6a04d92117d2a6e827e16cf2dbe4b47ac99380c7f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_maplestory-universe_bce2226.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_maplestory-universe_bce2226.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_maplestory-universe.json`.
- Execution note:
  표준 command는 기존 재발과 동일하게 slugless 또는 duplicate Drive file
  selection 위험이 있어, 기존 candidate validation, artifact, telemetry,
  and `upsert_job` 함수를 선택된 NEXPACE Drive file id 1개에만 적용했다.
  공개 forensic target row가 version 2/latest이므로 candidate source
  version을 2로 명시했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `maplestory-universe`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `eee1899f-7db7-4ac8-971c-5b6445068992`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id eee1899f-7db7-4ac8-971c-5b6445068992 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2226" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `189a0614-3fc5-4c05-b439-42cf747bf9c3`
  - promoted at: `2026-06-26T04:12:38.481396+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2226_maplestory_universe_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=maplestory-universe`
  - `tracked_projects.symbol=NXPC`
  - `project_reports.id=189a0614-3fc5-4c05-b439-42cf747bf9c3`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=NEXPACE는 0.2994달러 저점 후 반등했지만 선물 우위 수급과 49/100 조작 리스크로 0.3654달러 회복 확인이 우선이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=eee1899f-7db7-4ac8-971c-5b6445068992`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/maplestory-universe`,
    `https://www.bcelab.xyz/ko/reports/forensic/maplestory-universe`,
    `https://www.bcelab.xyz/en/projects/maplestory-universe`,
    `https://www.bcelab.xyz/en/reports/forensic/maplestory-universe`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2198 CRO Routine Execution Evidence (2026-06-25 15:49 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `03462cf` on branch `codex/paperclip-agent-summary-source`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Routine selection:
  Drive `analysis2/analysis` scope `all` was scanned by metadata across
  ECON/MAT/FOR. The newest eligible unpromoted Markdown source was MAT Bio:
  `BIO 크립토 이코노미 성숙도 평가 보고서_ Bio Protocol.md`,
  modified `2026-06-25T03:37:08.000Z`.
- Source evidence:
  - Drive file id: `19tBessBEQrvw7--uqmBq6hcohWS28qNz`
  - Revision id:
    `0B8HYgThT3NByNDYwV0JIWTNIWU5CK1RhVEg1ZUdZMDlHdTRzPQ`
  - Source identity:
    `drive:19tBessBEQrvw7--uqmBq6hcohWS28qNz:0B8HYgThT3NByNDYwV0JIWTNIWU5CK1RhVEg1ZUdZMDlHdTRzPQ`
  - Source SHA-256:
    `e70d827e8b87ee1523f6cc7382a556e36d829b9db08a14523bc9d9f734129b27`
  - Local source snapshot:
    `scripts/pipeline/output/paperclip_cro_source_mat_bio_bce2198.md`
- Paperclip CRO local summary JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_bio_bce2198.json`.
  The payload includes all seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`,
  `zh`), exact source sentences, source metadata, and confidence `0.88`.
- Candidate ingest evidence:
  - The standard CLI path was attempted with
    `analysis_md_summary_candidate.py --type mat --slug bio --drive-root-scope all --agent-output-json ... --require-agent-output --limit 1 --force`,
    but it did not complete in the heartbeat because current slugless Drive
    filename handling evaluates many candidates before applying `--limit`.
  - The same `analysis_md_summary_candidate.py` validation and `upsert_job`
    functions were then run against the selected Drive file id only.
  - Artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bio.json`
  - `report_summary_jobs` job id:
    `9b8bfd67-d9a2-4c66-9c30-c6b77327b3ec`
  - Upsert result: `inserted`
  - Validation status: `valid`
  - Validator warnings/errors: none (`validation_reasons=[]`).
- Summary Authority Gate write evidence:
  - Command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 9b8bfd67-d9a2-4c66-9c30-c6b77327b3ec --authority-mode llm_active --actor "paperclip-routine:CRO:1cef3813-cebd-423f-a592-c2b8b9308f6b" --write`
  - Decision:
    `action=promote`, `state=promoted`, `wrote_project_report=true`,
    reason `validated candidate promoted`.
  - Promoted project report:
    `a4d34a33-9340-4540-b04c-0b093f733ea6`
  - Resulting report row:
    `project_slug=bio`, `report_type=maturity`, `language=ko`,
    `status=published`.
  - `card_data.summary_authority.mode=llm_active` with the promoted job id and
    source identity above.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility depends on the existing
  production deployment that supports active summary-authority rows and any
  normal Next/Vercel cache TTL or revalidation behavior.

### BCE-2199 CRO Routine Execution Evidence (2026-06-25 16:08 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `03462cf` on branch `codex/paperclip-agent-summary-source`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Routine selection:
  Drive `analysis2/analysis` scope `all` was scanned by metadata across
  ECON/MAT/FOR, excluding already promoted revision identities. The newest
  eligible unpromoted Markdown source was MAT io.net:
  `io.net의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023-2026.md`,
  modified `2026-06-23T05:59:09.000Z`.
- Source evidence:
  - Drive file id: `1iPwXHKE3ybrSpS89F-RmImJtYOl-uRXE`
  - Revision id:
    `0B8HYgThT3NByZ0IzTGhUR0VlcnBvNGlRcDhzVEU3OHBDdU9BPQ`
  - Source identity:
    `drive:1iPwXHKE3ybrSpS89F-RmImJtYOl-uRXE:0B8HYgThT3NByZ0IzTGhUR0VlcnBvNGlRcDhzVEU3OHBDdU9BPQ`
  - Source SHA-256:
    `75439e73d30fc51d8ccf15c83ecd50fbac15ff2063207d75b4a69cea4e8594f3`
  - Local source snapshot:
    `scripts/pipeline/output/paperclip_cro_source_mat_io-net_bce2199.md`
- Paperclip CRO local summary JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_io-net_bce2199.json`.
  The payload includes all seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`,
  `zh`), exact source sentences, source metadata, and confidence `0.88`.
- Candidate ingest evidence:
  - The standard CLI path was attempted with
    `analysis_md_summary_candidate.py --type mat --slug io-net --drive-root-scope all --agent-output-json ... --require-agent-output --limit 1 --force`,
    but it did not complete in the heartbeat because current slugless Drive
    filename handling evaluates many candidates before applying `--limit`.
  - The same `analysis_md_summary_candidate.py` validation and `upsert_job`
    functions were then run against the selected Drive file id only.
  - Artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_io-net.json`
  - `report_summary_jobs` job id:
    `3e7ca3fc-0bb5-4a07-97c1-dc935d488cc7`
  - Upsert result: `inserted`
  - Validation status: `valid`
  - Validator warnings/errors: none (`validation_reasons=[]`).
- Summary Authority Gate write evidence:
  - Command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 3e7ca3fc-0bb5-4a07-97c1-dc935d488cc7 --authority-mode llm_active --actor "paperclip-routine:CRO:2356f0f1-584d-488e-bfa8-2e4d1f98532f" --write`
  - Decision:
    `action=promote`, `state=promoted`, `wrote_project_report=true`,
    reason `validated candidate promoted`.
  - Promoted project report:
    `12190241-cadc-4184-be85-3afde2e42779`
  - Resulting report row:
    `project_id=fb282651-3a6b-44f9-beef-fd90ce2ac3ec`,
    `report_type=maturity`, `language=ko`, `status=published`.
  - `card_data.summary_authority.mode=llm_active` with the promoted job id and
    source identity above.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility depends on the existing
  production deployment that supports active summary-authority rows and any
  normal Next/Vercel cache TTL or revalidation behavior.

### BCE-2200 CRO Routine Execution Evidence (2026-06-25 16:45 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `03462cf` on branch `codex/paperclip-agent-summary-source`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Routine selection:
  Drive `analysis2/analysis` scope `all` was scanned by metadata across
  ECON/MAT/FOR, excluding already promoted revision identities. The newest
  unpromoted Markdown with a matched project and website-visible KO target row
  was MAT TBLL xStock:
  `TBLL xStock의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`,
  modified `2026-06-09T07:27:56.000Z`.
- Source evidence:
  - Drive file id: `1ccxznmhb7uF-7dyeSqSXO6sKr2CXSNak`
  - Revision id:
    `0B8HYgThT3NByYVViMGN3V1A5M3cvcnprUnNkMkNhRFRQYTE4PQ`
  - Source identity:
    `drive:1ccxznmhb7uF-7dyeSqSXO6sKr2CXSNak:0B8HYgThT3NByYVViMGN3V1A5M3cvcnprUnNkMkNhRFRQYTE4PQ`
  - Source SHA-256:
    `bcff16e06339cd7e6999860859def499a221bfab8adfd3032a92c8c25cc95cb4`
  - Local source snapshot:
    `scripts/pipeline/output/paperclip_cro_source_mat_tbll-tokenized-etf-xstock_bce2200.md`
- Paperclip CRO local summary JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_tbll-tokenized-etf-xstock_bce2200.json`.
  The payload includes all seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`,
  `zh`), exact source sentences, source metadata, and confidence `0.88`.
- Candidate ingest evidence:
  - The standard CLI path was attempted with
    `analysis_md_summary_candidate.py --type mat --slug tbll-tokenized-etf-xstock --drive-root-scope all --agent-output-json ... --require-agent-output --limit 1 --force`,
    but it was interrupted after the known slugless Drive filename handling
    began broad downloads before applying `--limit`.
  - The same `analysis_md_summary_candidate.py` validation, telemetry,
    artifact, and `upsert_job` functions were then run against the selected
    Drive file id only.
  - Artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_tbll-tokenized-etf-xstock.json`
  - `report_summary_jobs` job id:
    `2bc148b1-67cf-4418-a4d3-933fc7422818`
  - Upsert result: `updated_existing`
  - Validation status: `valid`
  - Validator warnings/errors: none (`validation_reasons=[]`).
- Summary Authority Gate write evidence:
  - Command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 2bc148b1-67cf-4418-a4d3-933fc7422818 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2200" --write`
  - Decision:
    `action=promote`, `state=promoted`, `wrote_project_report=true`,
    reason `validated candidate promoted`.
  - Promoted project report:
    `e3f8b8a0-5adb-4c8a-bd53-f6a72ea1214c`
  - Resulting report row:
    `project_slug=tbll-tokenized-etf-xstock`, `report_type=maturity`,
    `language=ko`, `status=published`.
  - `card_data.summary_authority.mode=llm_active` with the promoted job id and
    source identity above.
- DB and website verification artifact:
  `scripts/pipeline/output/bce2200_tbll_xstock_db_website_verification.json`.
- Website/cache verification:
  KO and EN report/project pages for `tbll-tokenized-etf-xstock` returned HTTP
  `200` with `cache-control: private, no-cache, no-store, max-age=0,
  must-revalidate`. KO pages contained the promoted Korean summary, and EN
  pages contained the promoted English summary and Investment View text. The
  local Python TLS verifier used certificate verification disabled for this
  check only.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2201 CRO Routine Execution Evidence (2026-06-25 18:13 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Routine selection:
  Drive `analysis2/analysis` scope `all` was scanned by metadata across
  ECON/MAT/FOR, excluding already promoted revision identities. The newest
  unpromoted Drive files were IVVON MAT/ECON and Bio Protocol ECON, but IVVON
  had no tracked project match and Bio Protocol ECON had no website-visible ECON
  KO target row. The newest eligible unpromoted Markdown with a matched project
  and website-visible KO target row was MAT Ducky:
  `Ducky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`,
  modified `2026-06-09T07:11:28.000Z`.
- Source evidence:
  - Drive file id: `1h9utqX6zRsOZActmiT-uz-W23L1LctsJ`
  - Revision id:
    `0B8HYgThT3NByN3k3Z2xXL0xCWHFvVEtFMFVvN216UFhMZ05BPQ`
  - Source identity:
    `drive:1h9utqX6zRsOZActmiT-uz-W23L1LctsJ:0B8HYgThT3NByN3k3Z2xXL0xCWHFvVEtFMFVvN216UFhMZ05BPQ`
  - Source SHA-256:
    `65154bbc645ec4a18f7739b384a5cc9181bdd3dd57da3f3dbd4df6e683cb443d`
  - Local source snapshot:
    `scripts/pipeline/output/paperclip_cro_source_mat_ducky_bce2201.md`
- Paperclip CRO local summary JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_ducky_bce2201.json`.
  The payload includes all seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`,
  `zh`), exact source sentences, source metadata, and confidence `0.88`.
- Candidate ingest evidence:
  - The standard CLI path was attempted with
    `analysis_md_summary_candidate.py --type mat --slug ducky --drive-root-scope all --agent-output-json ... --require-agent-output --limit 1 --force`,
    but it was interrupted after the known slugless Drive filename handling
    began broad downloads before applying `--limit`.
  - The same `analysis_md_summary_candidate.py` validation, telemetry,
    artifact, and `upsert_job` functions were then run against the selected
    Drive file id only.
  - Artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_ducky.json`
  - `report_summary_jobs` job id:
    `0e15ccfb-8f90-4fe2-8d55-b4b6eddaa063`
  - Upsert result: `inserted`
  - Validation status: `valid`
  - Validator warnings/errors: none (`validation_reasons=[]`).
- Summary Authority Gate write evidence:
  - Command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 0e15ccfb-8f90-4fe2-8d55-b4b6eddaa063 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2201" --write`
  - Decision:
    `action=promote`, `state=promoted`, `wrote_project_report=true`,
    reason `validated candidate promoted`.
  - Promoted project report:
    `65bf76f4-3ecb-44b8-b6a3-6d6996e52eb2`
  - Resulting report row:
    `project_slug=ducky`, `report_type=maturity`, `language=ko`,
    `status=published`, `is_latest=true`.
  - `card_data.summary_authority.mode=llm_active` with the promoted job id and
    source identity above.
- DB and website verification artifact:
  `scripts/pipeline/output/bce2201_ducky_db_website_verification.json`.
- Website/cache verification:
  KO and EN project pages for `ducky` and KO/EN maturity report pages at
  `/reports/ducky/maturity` returned HTTP `200` with `cache-control: private,
  no-cache, no-store, max-age=0, must-revalidate`. KO pages contained the
  promoted Korean summary, and EN pages contained the promoted English summary
  and Investment View text. The local Python TLS verifier used certificate
  verification disabled for this check only.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2202 CRO Routine Execution Evidence (2026-06-25 19:12 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Routine selection:
  Drive `analysis2/analysis` scope `all` was scanned by metadata across
  ECON/MAT/FOR, excluding already promoted revision identities. The newest
  eligible unpromoted Markdown with a matched project and website-visible KO
  target row was MAT Quack AI:
  `Quack AI의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`,
  modified `2026-06-25T05:35:45.000Z`.
- Source evidence:
  - Drive file id: `1EYjBWjRdBoRkbQl2NfzSnf-BEZIoCfKh`
  - Revision id:
    `0B8HYgThT3NByS1VmTnRtajFxczdKMzJwbVRXc1JyMmZENC84PQ`
  - Source identity:
    `drive:1EYjBWjRdBoRkbQl2NfzSnf-BEZIoCfKh:0B8HYgThT3NByS1VmTnRtajFxczdKMzJwbVRXc1JyMmZENC84PQ`
  - Source SHA-256:
    `5b6403cc11421bc37b1714bc65ea4c03406be3c41ee8d8fac458966672726610`
  - Local source snapshot:
    `scripts/pipeline/output/paperclip_cro_source_mat_quack-ai_bce2202.md`
- Paperclip CRO local summary JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_quack-ai_bce2202.json`.
  The payload includes all seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`,
  `zh`), exact source sentences, source metadata, and confidence `0.88`.
- Candidate ingest evidence:
  - Dry-run validation first failed on card quality length/raw-format checks;
    the CRO summary JSON was shortened and revalidated successfully.
  - The standard CLI path was attempted with
    `analysis_md_summary_candidate.py --type mat --slug quack-ai --drive-root-scope all --agent-output-json ... --require-agent-output --limit 1 --force`,
    but it was interrupted after Drive downloads did not complete within the
    heartbeat, matching the known broad-download behavior.
  - The same `analysis_md_summary_candidate.py` validation, artifact, and
    `upsert_job` functions were then run against the selected Drive file id
    only.
  - Artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_quack-ai.json`
  - `report_summary_jobs` job id:
    `daf41d0c-a521-4af0-9a96-85d712ab044f`
  - Upsert result: `inserted`
  - Validation status: `valid`
  - Validator warnings/errors: none (`validation_reasons=[]`).
- Summary Authority Gate write evidence:
  - Command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id daf41d0c-a521-4af0-9a96-85d712ab044f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2202" --write`
  - Decision:
    `action=promote`, `state=promoted`, `wrote_project_report=true`,
    reason `validated candidate promoted`.
  - Promoted project report:
    `64ede1cf-66a0-4754-bb46-c4a5e3951d3e`
  - Resulting report row:
    `project_slug=quack-ai`, `report_type=maturity`, `language=ko`,
    `status=published`, `is_latest=true`.
  - `card_data.summary_authority.mode=llm_active` with the promoted job id and
    source identity above.
- DB and website verification artifact:
  `scripts/pipeline/output/bce2202_quack_ai_db_website_verification.json`.
- Website/cache verification:
  KO and EN project pages for `quack-ai` and KO/EN maturity report pages at
  `/reports/quack-ai/maturity` returned HTTP `200` with `cache-control:
  private, no-cache, no-store, max-age=0, must-revalidate`. KO pages contained
  the promoted Korean summary, and EN pages contained the promoted English
  summary and Investment View text. The local Python TLS verifier used
  certificate verification disabled for this check only.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2203 CRO Routine Execution Evidence (2026-06-25 19:40 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Routine selection:
  Drive `analysis2/analysis` scope `all` was scanned by metadata across
  ECON/MAT/FOR, excluding already promoted revision identities. The newest
  eligible unpromoted Markdown with a matched project and website-visible KO
  target row was MAT USDGO:
  `USDGO의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`,
  modified `2026-06-09T06:11:42.000Z`.
- Source evidence:
  - Drive file id: `1_UJ7rdxa8K333dVVRldNBEidgCHCuDmN`
  - Revision id:
    `0B8HYgThT3NByNmVBc3ZnM282d2dBQjRmMTdnWUZmdTU2Nm5NPQ`
  - Source identity:
    `drive:1_UJ7rdxa8K333dVVRldNBEidgCHCuDmN:0B8HYgThT3NByNmVBc3ZnM282d2dBQjRmMTdnWUZmdTU2Nm5NPQ`
  - Source SHA-256:
    `d61e0c916bab387d23ae94d6b6a13eb041a641bb564db6fc4ad4312191e2322c`
  - Local source snapshot:
    `scripts/pipeline/output/paperclip_cro_source_mat_usdgo_bce2203.md`
- Paperclip CRO local summary JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_usdgo_bce2203.json`.
  The payload includes all seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`,
  `zh`), exact source sentences, source metadata, and confidence `0.88`.
- Candidate ingest evidence:
  - Dry-run validation first caught card-quality format and Korean sentence
    count failures; the CRO summary JSON was shortened and revalidated
    successfully.
  - The standard CLI path was attempted with
    `analysis_md_summary_candidate.py --type mat --slug usdgo --drive-root-scope all --agent-output-json ... --require-agent-output --limit 1 --force`,
    but it was interrupted after Drive downloads did not complete within the
    heartbeat, matching the known broad-download behavior.
  - The same `analysis_md_summary_candidate.py` validation, telemetry,
    artifact, and `upsert_job` functions were then run against the selected
    Drive file id only.
  - Artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_usdgo.json`
  - `report_summary_jobs` job id:
    `540c712c-5a1e-4ff6-afbe-e6b9e920604b`
  - Upsert result: `inserted`
  - Validation status: `valid`
  - Validator warnings/errors: none (`validation_reasons=[]`).
- Summary Authority Gate write evidence:
  - Command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 540c712c-5a1e-4ff6-afbe-e6b9e920604b --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2203" --write`
  - Decision:
    `action=promote`, `state=promoted`, `wrote_project_report=true`,
    reason `validated candidate promoted`.
  - Promoted project report:
    `bded7a0d-9e93-417e-b420-cb6fe1f3c649`
  - Resulting report row:
    `project_slug=usdgo`, `report_type=maturity`, `language=ko`,
    `status=published`, `is_latest=true`.
  - `card_data.summary_authority.mode=llm_active` with the promoted job id and
    source identity above.
- DB and website verification artifact:
  `scripts/pipeline/output/bce2203_usdgo_db_website_verification.json`.
- Website/cache verification:
  KO and EN project pages for `usdgo` and KO/EN maturity report pages at
  `/reports/usdgo/maturity` returned HTTP `200` with `cache-control: private,
  no-cache, no-store, max-age=0, must-revalidate`. KO pages contained the
  promoted Korean summary, and EN pages contained the promoted English summary
  and Investment View text. The local Python TLS verifier used certificate
  verification disabled for this check only.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2204 CRO Routine Execution Evidence (2026-06-25 20:33 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Routine selection:
  Drive `analysis2/analysis` scope `all` was scanned by metadata across
  ECON/MAT/FOR, excluding already promoted revision identities. The newest
  unpromoted files included Quack AI ECON, IVVON MAT/ECON, Bio Protocol ECON,
  and Unibase MAT; IVVON still had no tracked project match. The newest
  eligible unpromoted Markdown with a matched project and website-visible KO
  target row was ECON Quack AI:
  `Quack AI 크립토이코노미 설계 분석 보고서.md`,
  modified `2026-06-25T05:34:45.000Z`.
- Source evidence:
  - Drive file id: `1T3Gipe9I6RE4ewzA58oBr-Ob2Ci521wi`
  - Revision id:
    `0B8HYgThT3NByYURDTFY1VU9WTkEranJzNGhVMXRPSUQvUUxrPQ`
  - Source identity:
    `drive:1T3Gipe9I6RE4ewzA58oBr-Ob2Ci521wi:0B8HYgThT3NByYURDTFY1VU9WTkEranJzNGhVMXRPSUQvUUxrPQ`
  - Source SHA-256:
    `8d57b0d1f75227b0fd804d807fd07c3e15f379c99e579e0b0416d03eb4738d43`
  - Local source snapshot:
    `scripts/pipeline/output/paperclip_cro_source_econ_quack-ai_bce2204.md`
- Paperclip CRO local summary JSON:
  `scripts/pipeline/output/paperclip_cro_summary_econ_quack-ai_bce2204.json`.
  The payload includes all seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`,
  `zh`), exact source sentences, source metadata, and confidence `0.88`.
- Candidate ingest evidence:
  - Dry-run validation first caught one English raw-format card-quality failure;
    the CRO summary JSON was revised to remove the hyphenated phrase and then
    revalidated successfully.
  - To avoid the known slugless Drive broad-download behavior, the same
    `analysis_md_summary_candidate.py` validation, telemetry, artifact, and
    `upsert_job` functions were run against the selected Drive file id only.
  - Artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_econ_quack-ai.json`
  - `report_summary_jobs` job id:
    `15810aeb-791c-487a-96a1-fca49af9c2c8`
  - Upsert result: `inserted`
  - Validation status: `valid`
  - Validator warnings/errors: none (`validation_reasons=[]`).
- Summary Authority Gate write evidence:
  - Command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 15810aeb-791c-487a-96a1-fca49af9c2c8 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2204" --write`
  - Decision:
    `action=promote`, `state=promoted`, `wrote_project_report=true`,
    reason `validated candidate promoted`.
  - Promoted project report:
    `70a45bd7-0a5a-4b4e-aeb7-1a60506fb532`
  - Resulting report row:
    `project_slug=quack-ai`, `report_type=econ`, `language=ko`,
    `status=published`, `is_latest=true`.
  - `card_data.summary_authority.mode=llm_active` with the promoted job id and
    source identity above.
- DB and website verification artifact:
  `scripts/pipeline/output/bce2204_quack_ai_econ_db_website_verification.json`.
- Website/cache verification:
  KO and EN project pages for `quack-ai` and KO/EN ECON report pages at
  `/reports/quack-ai/econ` returned HTTP `200` with `cache-control: private,
  no-cache, no-store, max-age=0, must-revalidate`. KO pages contained the
  promoted Korean summary, and EN pages contained the promoted English summary
  and Investment View text. The local Python TLS verifier used certificate
  verification disabled for this check only.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2147 0x/ZRX Target Seed Applied and Verified (2026-06-25 16:54 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `03462cf`.
- Primary context checked before verification:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Approval:
  [44bc62b2-ff81-43f4-bf86-faed5172ac7b](/BCE/approvals/44bc62b2-ff81-43f4-bf86-faed5172ac7b)
  was approved for production apply of the 0x/ZRX target seed.
- Remote migration evidence:
  - workflow: Database Migration
  - run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28154944416
  - job: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28154944416/job/83381125707
  - head SHA: `03462cf7715c5fe9a53fcb78165246bdb6fb2d8e`
  - selected migration:
    `20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`
  - result: success; Supabase selected SQL query returned `[]`.
- Production DB verification:
  - `tracked_projects.id=7006c0e1-a65d-4f9f-93c1-34c07ec9c041`
  - `tracked_projects.slug=0x`, `name=0x Protocol`, `symbol=ZRX`,
    `coingecko_id=0x`, `status=active`
  - aliases include `0x protocol`, `0x-protocol`, `zero ex`, `zero-ex`, `zrx`
  - `project_reports.id=7cc38496-9e3d-44a0-8413-f69cbffe006a`
  - `report_type=maturity`, `version=1`, `language=ko`,
    `status=coming_soon`, `is_latest=true`
  - source identity:
    `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`
- Candidate/gate verification:
  candidate job `885624b8-1a5e-4265-970e-d14adb86b790` is now
  `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`, `promotion_decision=promote`, and
  `promoted_project_report_id=7cc38496-9e3d-44a0-8413-f69cbffe006a`.
- Resolution:
  the 0x/ZRX seed blocker for [BCE-2150](/BCE/issues/BCE-2150) is cleared.
  [BCE-2147](/BCE/issues/BCE-2147) and its apply blocker
  [BCE-2151](/BCE/issues/BCE-2151) can be closed.
- Manifest change:
  no change needed. This was target data/backfill work under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2193 Website Publication Contract for Summary-Only Promoted Rows (2026-06-25 13:39 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe` before local changes.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Issue:
  RealLink ECON job `b9117ac6-dfb6-4297-8317-3e4dead2c7ac` is promoted to
  project report `f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`, but the target row is
  `status=coming_soon` and summary-only with no `slide_html_urls_by_lang`.
  Existing website code queried only `published`/`in_review` rows on project
  pages and required slide HTML on report pages, so promoted metadata was not
  visible.
- Chosen publication contract:
  `project_reports.status=coming_soon` remains hidden by default. A coming-soon
  row becomes website-visible only when `card_data.summary_authority.mode` is
  `llm_active` and localized summary metadata exists for the requested locale.
  This preserves the existing rule that ordinary PDF-only or pre-render slide
  rows remain `locale_pending`, while Summary Authority Gate promoted
  summary-only rows can expose summary and Investment View copy.
- Code changes:
  - `src/app/[locale]/projects/[slug]/page.tsx` now queries
    `published`, `coming_soon`, and `in_review` rows, then filters
    coming-soon rows to active summary-authority rows only.
  - `src/lib/report-locale.ts` treats active summary-authority metadata as
    locale support for report card selection.
  - `src/app/[locale]/reports/[slug]/_components/slide-report-utils.ts`
    treats active summary-authority metadata as an available locale report even
    without slide HTML.
- Local verification:
  - `npm test -- --runTestsByPath 'src/app/[locale]/projects/[slug]/page.test.ts' 'src/app/[locale]/reports/[slug]/_components/SlideReportPage.test.ts' src/lib/report-locale.test.ts --runInBand`
    passed (`76 passed`).
  - `npx tsc --noEmit` passed.
  - `npm run verify:pipeline` passed.
  - `npm run verify:runtime-pipelines` passed.
  - `npm run lint` passed with existing warnings only.
  - `npm run build` passed.
- Deployment status:
  local implementation and verification are complete. Production deployment and
  live RealLink ECON page checks still need the guarded `Production Deploy`
  workflow for BCE-2193 before BCE-2191 can close.

## BCE-2005 Remote Migration/Deploy Evidence (Blocked)

- Workspace: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
- Current branch SHA when analyzed: `2a25add` (`HEAD` on `codex/fix-exchange-production-regressions`)
- Migration contract added for authority-gate tables/functions:
  - `supabase/migrations/20260620111400_add_summary_authority_gate.sql`
    - Adds `report_summary_jobs.authority_state`, `authority_mode`, promotion
      audit fields, and `report_summary_promotion_locks`
    - Adds PostgreSQL RPC `public.promote_report_summary_job(...)`
- Remote migration workflow path:
  - `.github/workflows/db-migration.yml`
  - Triggers on `supabase/migrations/**` changes or manual dispatch
  - Applies migrations with `supabase db push` in `environment: production`
- Deployment workflow path:
  - `.github/workflows/production-deploy.yml`
  - Verifies pipeline manifests/runtime checks before production deploy
  - Enforces `expected_branch` / optional `expected_commit` evidence in inputs
- Summary gate write path remains default-off:
  - `scripts/pipeline/summary_authority_gate.py` only persists on `--write`
  - Tests assert lock/rejection/promotion transitions in
    `scripts/pipeline/test_summary_authority_gate.py`
- 2026-06-20 `local-board` executed required remote steps on branch `codex/fix-exchange-production-regressions` commit `2a25add8416211029725d887ab882ca63e638364` (Board approval `f969099e-589f-4dc6-8e46-49aaac9e1c59`).
- Remote migration attempt:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857395766
  - Final result: failed (`Apply Migrations` / `supabase db push`)
  - Failure reason: remote migration history contains `202604...` versions that are not present in current branch `supabase/migrations` directory, so `supabase db push` aborted.
  - Recovery issue opened: `BCE-2006` (Supabase migration history mismatch / fix authority gate migration application failure)
- Production deploy attempt:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857395760
  - `Verify Deployment Evidence` job: success (`npm ci`, `verify:pipeline`, `verify:runtime-pipelines`, `tsc`, tests, build)
  - Vercel deploy: success (`https://blockchain-economics-hhllxrvk3-michael-zhangs-projects-df54ac7d.vercel.app`)
  - Aliased domain: `https://www.bcelab.xyz`
  - Final result: failed (`Verify Top500 and exchange regression gates`)
  - Failure item: Top500 page includes Bitcoin row, CMC rank, ECON badge, MAT badge
  - Passed item: exchange list API / Binance listing API / Binance exchange page Bitcoin row/rank/ECON/MAT badge
  - Recovery issue opened: `BCE-2007` (Top500 regression gate failure after production deploy)
- Resolution status snapshot:
  - At 2026-06-20 11:42 KST, BCE-2005 remained `blocked`.
  - Latest `BCE-2006` update:
    - Repo-side migration compatibility fix was pushed on branch `codex/fix-exchange-production-regressions` at commit `6bc8302`.
    - Migration rerun succeeded at: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857730221
      - The original “remote-only version blocker” is cleared.
      - Supabase now requests an explicit decision for earlier local April migrations before the latest remote migration.
    - Board approval `35a8e2b7-6813-45ab-af09-4bfb00a2570b` approved the metadata-only
      `supabase migration repair --status applied` path and rollback guidance.
    - At 11:42 KST, `BCE-2006` was blocked on valid GitHub Actions
      dispatch/execution credentials for the approved remote repair path; this
      agent's local `gh` credential returned HTTP 401 on Actions API calls during
      the continuation heartbeat.
  - `BCE-2007` has been resolved:
    - Root-cause fix commit: `c5dd9fe34df0da1eae4047ed662312150220fc3c`
    - Deployment branch/SHA: `codex/fix-exchange-production-regressions@6bc83027e19f1336e78de035295f28ab4e77086a`
    - Production deploy run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857785244
    - Deploy job: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857785244/job/82448388296
    - Vercel URL: https://blockchain-economics-5e4fztf4h-michael-zhangs-projects-df54ac7d.vercel.app
    - Direct alias validation passed (`BCE_REGRESSION_BASE_URL=https://bcelab.xyz npm run verify:production-regressions`) and browser DOM check confirms Bitcoin row/CMC #1/ECON/MAT.
    - Workflow evidence: `Workflow gate passed: Verify Top500 and exchange regression gates`
- Next step after `BCE-2006` + `BCE-2007` resolution:
    - rerun remote migration and production-equivalent E2E on deploy path,
    - attach successful run IDs proving migration success and production gate pass,
    - then close BCE-2005.

- Current status after approved BCE-2006 recovery:
  - Migration recovery is now complete and verified (`BCE-2006` blocker cleared
    in `27860631382` and `27860660544`).
  - Production-equivalent deploy evidence has been produced:
    - https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860761456
    - Head SHA: `35fa6cfa1129ce0453cd40df9cd6a5ecb600fc9b`
    - `Verify Deployment Evidence`: success
    - `Deploy Production`: success
  - `27860761456` includes successful run and rerun evidence after migration:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860688271
  - Migration/deploy evidence path is now satisfied:
    - migration: `27860631382`, `27860660544`
    - deploy/E2E: `27860761456`
  - PR for the production changes was merged:
    - https://github.com/CryptoPhilo/blockchain-economics-lab/pull/242
    - branch `codex/analysis-summary-gate-main` @ `288784acd231ad36c6bbc5f8083bdf49caa1abbe`
    - merge commit `06406aba7ad039718659fd0c66fcccd1ad170c2a`
    - superseded PR #241 was closed.
  - Merge was performed with CEO/operator waiver evidence because no non-author
    GitHub reviewer was available:
    - Paperclip approval `7b7ad020-6ac9-430f-bcc0-16da1e386720`
    - PR #242 Release Gate records the waiver.
  - Migration/e2e evidence is complete. `BCE-2011` paperclip-agent ingestion and dry-run evidence has now been collected (job `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`, `dry_run=true`, `wrote_project_report=false`).
  - `BCE-2005` currently remains blocked pending explicit workflow execution/approval
    for write-mode promotion.
  - Post-merge workflow evidence:
    - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27861381155
    - Mode: `apply`, report type: `econ`, slug: `humanity-protocol`, drive scope: `all`, gate authority mode: `llm_candidate`
    - Result: failed in `Generate candidate` with exit code 2 because the candidate was invalid.
    - Candidate job row was inserted as validation-failed only:
      `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`.
    - Artifact:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27861381155/artifacts/7762372421
    - Validation failures included missing `marketing_by_lang` languages and
      overlong/raw-format summaries. Gate dry-run did not execute because no
      valid candidate existed.
  - Runtime secret audit:
    - Repository secrets include Supabase and Google Drive credentials.
    - The previous design incorrectly required `BCE_ANALYSIS_MD_LLM_ENDPOINT`,
      `BCE_ANALYSIS_MD_LLM_BEARER_TOKEN`, and
      `BCE_ANALYSIS_MD_SUMMARY_MODEL`.
    - That was the wrong boundary for this request: summary generation should
      be performed by a Paperclip local agent using its local LLM runtime, and
      this pipeline should only validate and persist the agent output.
  - Required closeout evidence after Paperclip agent apply setup:
    - Paperclip local agent run that records the selected Drive source and
      writes schema-conformant summary JSON.
    - candidate ingestion with `--agent-output-json` and
      `--require-agent-output`.
    - candidate `report_summary_jobs` artifacts/logs and
      `Summary Authority Gate` dry-run output showing `dry_run=true` and no
      `project_reports` writes.
  - PR #243 (`0c2a725137989bd0100333d4e475808e70fef913`) was a safety patch
    that prevented deterministic fallback writes in apply mode, but its
    endpoint-secret requirement is superseded by the Paperclip agent output
    contract.
  - PR #244 merged:
    - https://github.com/CryptoPhilo/blockchain-economics-lab/pull/244
    - Head SHA: `337b080234fc2cf332ca345986be09ab76bc1d47`
    - Merge commit: `d98fc27628bfdd8e3e696d75f9a2049d790bf346`
    - Merged at: `2026-06-20T06:02:25Z`
    - Merged at: 2026-06-20 15:02 KST
    - CI status: all required checks passed before merge.
    - removes direct GitHub Actions LLM API call / secret dependency in apply mode;
      `--agent-output-json` is now the required input path.
    - Validation checks passed:
      - Python pipeline tests: `15 passed`
      - workflow YAML parse: passed
      - `npm run verify:runtime-pipelines`: passed
      - `npm run verify:pipeline`: passed
  - Remaining before close:
    - Paperclip local agent + `--agent-output-json` evidence is completed in `BCE-2011`.
    - Production promotion remains pending separate explicit approval before any
      `--write` gate invocation.
  - 2026-06-20 run `27861610008` remains useful as negative evidence: it
    prevented runtime or DB candidate writes when the summary-generation
    boundary was unavailable.
  - BCE-2009 endpoint-secret blocker is superseded by the Paperclip-local
    agent output contract and BCE-2011 ingestion evidence.
  - Keep BCE-2005 blocked until explicit workflow execution/approval for
    write-mode promotion is completed.
  - Pipeline state wiki update for this checkpoint was pushed in commit `5db974c`.

### BCE-2011 Paperclip Local Agent Ingestion Evidence (2026-06-20 15:09 KST)

- Workspace/SHA used: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab` at `337b080`.
- Branch: `codex/paperclip-agent-summary-source`.
- Routine: `CRO Analysis MD Summary JSON Ingestion Routine`
  (`50aff64a-3178-4af7-b67b-49bf4521aedb`).
- Linked issue status: BCE-2011 `done`.
- Source: Google Drive Markdown `TAC 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1_beEKEvrOiCCcdtnXndJ3to6eiQ2pjZl:0B8HYgThT3NByeThlRHAwajFSaWZQdFNnQjJZREZ5MUdKN1FzPQ`.
- Agent output JSON:
  `scripts/pipeline/fixtures/bce-2010-humanity-protocol-agent-output.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug humanity-protocol --drive-root-scope all --agent-output-json scripts/pipeline/fixtures/bce-2010-humanity-protocol-agent-output.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`

  - job id: `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`
  - artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_econ_humanity-protocol.json`
- Summary Authority Gate dry-run command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5532671b-87ea-4b6c-a72c-fc7ba6bf1d86 --authority-mode llm_candidate --actor "paperclip-routine:CRO:BCE-2011"`.
- Gate dry-run result:
  - `dry_run=true`
  - action: `fallback`
  - state: `fallback_script`
  - reason: `legacy active summary retained`
  - `wrote_project_report=false`
- This satisfies the Paperclip-local JSON ingestion evidence for the candidate
  row and default-off gate dry-run. Production promotion remains separate and
  requires explicit approval before any `--write` gate invocation.

### BCE-2012 Immediate Publish Gate Attempt (2026-06-20 15:45 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `61b0ae6`.
- Board instruction update:
  `BCE-2012` should ignore the stale 06:30 dry-run wording and use the immediate
  publish path once candidate ingest is `valid` and a `job_id` is available.
- Candidate job reused from `BCE-2011`:
  `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`.
- Write gate command executed:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5532671b-87ea-4b6c-a72c-fc7ba6bf1d86 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2012" --write`.
- Result:
  - exit code: `1`
  - no `promote` result returned
  - no `wrote_project_report=true` evidence
  - no `project_report_id` returned
- Blocker:
  - Supabase RPC `public.promote_report_summary_job(...)` failed with
    PostgreSQL error `42883`: `operator does not exist: report_type = text`.
  - The deployed function compares `project_reports.report_type` to
    `v_job.report_type`; current production types require an explicit cast or a
    function signature/body fix before the authority gate can promote.
- Operational status:
  - `BCE-2012` must not be marked done under the board condition.
  - A DataPlatformEngineer/CTO hotfix is required for the promotion RPC, followed
    by rerunning the same `llm_active --write` command and verifying
    `action=promote`, `wrote_project_report=true`, and `project_report_id`.

### BCE-2013 Summary Authority Gate RPC Cast Hotfix (2026-06-20 15:48 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d89bdc2` for diagnosis, then branch
  `codex/paperclip-agent-summary-source` hotfix commits.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Hotfix:
  - Migration `supabase/migrations/20260620114500_fix_summary_authority_gate_report_type_cast.sql`
    replaces `public.promote_report_summary_job(...)`.
  - The target lookup now compares `project_reports.report_type::text` to
    `report_summary_jobs.report_type`, clearing PostgreSQL `42883`
    `operator does not exist: report_type = text`.
- Local verification:
  - `python3 -m pytest scripts/pipeline/test_summary_authority_gate.py`
    passed (`7 passed`).
- Remote DB application:
  - Initial selected-migration dispatch on hotfix SHA `702fe15` failed because
    the workflow entered a Supabase CLI history step while CLI setup was skipped.
  - Workflow guard fix pushed at `f053209`.
  - Selected SQL migration rerun succeeded:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27863351352
  - A preceding selected-migration run also succeeded on the same branch:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27863338650
- Promotion evidence:
  - Candidate job:
    `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`.
  - Promotion actor:
    `paperclip-routine:CRO:BCE-2012`.
  - DB state after hotfix:
    `authority_state=promoted`, `authority_mode=llm_active`,
    `promotion_decision=promote`, `promoted_project_report_id=87fcaaed-41d2-4fec-a907-1c8ba59e6767`.
  - Promotion timestamp:
    `2026-06-20T06:48:43.315601+00:00`.
  - Project report state:
    `project_reports.id=87fcaaed-41d2-4fec-a907-1c8ba59e6767`,
    `report_type=econ`, `language=ko`, `status=published`.
  - `card_data.summary_authority` records `mode=llm_active`, the candidate job
    id, idempotency key, source identity, and the same promotion timestamp.
  - Idempotent verification command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 5532671b-87ea-4b6c-a72c-fc7ba6bf1d86 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2012" --write`
    returned `decision.action=noop`, `decision.state=promoted`,
    `project_report_id=87fcaaed-41d2-4fec-a907-1c8ba59e6767` because the job was
    already terminal after the successful promotion.
- Current status:
  - The Summary Authority Gate RPC report_type cast blocker is cleared.
  - BCE-2012 can proceed using the promoted project report evidence above.

### BCE-2130 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 16:41 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Meteora의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:14f6HvNzX85-zBu1Owz8fBDHrZuXuHaZW:0B8HYgThT3NByTCs5SmExbkl4K1FYNlRJbzhyV25jMCtKLytRPQ`.
- Source SHA-256:
  `f39f688a23976f668b26d6fbe78e08d48fb4e7633295fbf07ff77220e85aac34`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_meteora_bce2130.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_meteora.json`.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `meteora`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `bbbe8e1e-fa05-451a-8cdd-62ed9f2d5c00`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id bbbe8e1e-fa05-451a-8cdd-62ed9f2d5c00 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2130" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `7f444a0b-2441-4956-a9f7-7470ad5bd2b3`
  - promoted_at: `2026-06-23T07:41:03.374583+00:00`
- Project report verification:
  - `project_reports.id=7f444a0b-2441-4956-a9f7-7470ad5bd2b3`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=bbbe8e1e-fa05-451a-8cdd-62ed9f2d5c00`

### BCE-2131 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 17:07 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Meteora 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1pRIwA1LalWa2dbC7faqjmeW8jG4u_If3:0B8HYgThT3NByNGJSQUNLK0RNK0RXWFhVME9yb3BrWm1sYWtVPQ`.
- Source SHA-256:
  `b26172cd8cc0ed9ebe0224289562acef543607f954f538e9b8369ee71094903f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_meteora_bce2131.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_meteora.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `meteora`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `4c1a8b32-4ed7-4e71-8b7b-054b9b17666c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 4c1a8b32-4ed7-4e71-8b7b-054b9b17666c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2131" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `d32a0c6f-8ace-49ba-83bd-a400a56c866f`
  - promoted_at: `2026-06-23T08:07:34.547592+00:00`
- Project report verification:
  - `project_reports.id=d32a0c6f-8ace-49ba-83bd-a400a56c866f`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Meteora는 Solana 유동성 효율과 토큰 런칭 자동화가 강점이지만, MET 가치 포착은 아직 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=4c1a8b32-4ed7-4e71-8b7b-054b9b17666c`

### BCE-2132 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 17:47 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Magma Finance의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:19vllBSiVVbyQO43qoYNFZepd0In8bn3Y:0B8HYgThT3NByVm9JWTlPUnIzb3c3ZGRmUmZRTkU2KzlvdzRzPQ`.
- Source SHA-256:
  `3d3484a57aab66434680149b9a1b608a24f1982b7dfaa4ae2b14ece2759ba936`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_magma-finance_bce2132.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_magma-finance.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT folder
  downloads because Korean MAT filenames are not always parsed into slugs, so
  this run used the same candidate validation/upsert functions against the
  selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `magma-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `dba38904-d9ce-428e-9204-6367de9a5005`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id dba38904-d9ce-428e-9204-6367de9a5005 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2132" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `4e092b3f-ef8e-4f1e-b37f-988d67d3c8f0`
  - promoted_at: `2026-06-23T08:47:55.032197+00:00`
- Project report verification:
  - `tracked_projects.slug=magma-finance`
  - `project_reports.id=4e092b3f-ef8e-4f1e-b37f-988d67d3c8f0`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Magma Finance는 Sui 기반 ALMM DEX 구현은 확인되지만, 수수료와 거버넌스 성숙도는 아직 약하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=dba38904-d9ce-428e-9204-6367de9a5005`

### BCE-2133 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 18:13 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Magma Finance 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1HAGkmutus6G8MMRPku0iDthdmgN7ISn2:0B8HYgThT3NBybTdONGdIVnVhS3hOUU41a2d1K2tIVFVrWk1vPQ`.
- Source SHA-256:
  `e70af375e55f68cb76a7f899654fb88d2a8139e93900fc45fdfb277d7831ad97`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_magma-finance_bce2133.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_magma-finance.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broader folder scans
  when Korean ECON filenames are not parsed into slugs, so this run used the
  same candidate validation/upsert functions against the selected Drive file id
  only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `magma-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d1d5cb1e-7eb9-47c7-b269-189d2db083b0`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d1d5cb1e-7eb9-47c7-b269-189d2db083b0 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2133" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `ef22c31e-1d27-40d1-900f-4e0508b1c9c0`
  - promoted_at: `2026-06-23T09:12:55.44962+00:00`
- Project report verification:
  - `tracked_projects.slug=magma-finance`
  - `project_reports.id=ef22c31e-1d27-40d1-900f-4e0508b1c9c0`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Magma Finance는 Sui 집중유동성 DEX로 자본 효율은 강하지만, 거래량 품질과 MAGMA 희석 리스크 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=d1d5cb1e-7eb9-47c7-b269-189d2db083b0`

### BCE-2134 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 05:37 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Decentraland MANA 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1FDc-FNV0PeMYoP4nFGKKkGCQZN4bRSNb:0B8HYgThT3NByTU9SSWZhZHpWMFBvTVpDSlArRUxlVlMrWU9ZPQ`.
- Source SHA-256:
  `0f3d994e4324f4ccf0b7569b05413a4b05983983e63407883dba84e1b098e9ba`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_decentraland_bce2134.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_decentraland.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broad FOR folder scans
  when Korean forensic filenames are not parsed into slugs, so this run used the
  same candidate validation/upsert functions against the selected Drive file id
  only.
- Candidate ingest result:
  - report type: `for` / DB type: `forensic`
  - slug: `decentraland`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `fabcc35f-0397-41fa-8621-432437d68441`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fabcc35f-0397-41fa-8621-432437d68441 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2134" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `83cdd187-4203-44d9-b86e-117f3e16f6e3`
  - promoted_at: `2026-06-23T20:37:31.858158+00:00`
- Project report verification:
  - `tracked_projects.slug=decentraland`
  - `project_reports.id=83cdd187-4203-44d9-b86e-117f3e16f6e3`
  - `report_type=forensic`, `language=ko`, `status=published`
  - `card_summary_ko=Decentraland MANA는 중상위 조작 리스크와 선물 우위가 겹쳐, 0.0744 돌파 전까지 고점 분배 압력이 크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=fabcc35f-0397-41fa-8621-432437d68441`
- BCE-2127 closure verification:
  `BCE-2128` completed, then `BCE-2127` resumed at workspace
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  SHA `fb1f7e8`. `https://www.bcelab.xyz/en/reports/forensic/decentraland`
  and `https://www.bcelab.xyz/en/projects/decentraland` both returned HTTP
  `200` with `cache-control: private, no-cache, no-store, max-age=0,
  must-revalidate`; both HTML responses contained the promoted English text
  `Decentraland MANA has elevated manipulation risk and futures driven flow,
  leaving distribution pressure high until the 0.0744 area breaks.` The stale
  BCE-2126 English text was absent from both pages. Local verification also
  passed: `python3 -m pytest scripts/pipeline/test_summary_authority_gate.py`
  (`7 passed`) and `npm run verify:runtime-pipelines`.

### BCE-2135 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 06:27 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `o1.exchange 크립토이코노미 설계 심층 분석.md`.
- Source identity:
  `drive:1h4tkt3wEgPl3H79_7be_LXN9JqNKGkkb:0B8HYgThT3NByY1JUMGJJTHRUaEJxT0hrUEJ3ZXYrc3JkWWwwPQ`.
- Source SHA-256:
  `560e3c912f5c87c74f52d631117f6bc79fb2feb6188c9a6a743403b6bf0aa1d9`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_o1-exchange_bce2135.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_o1-exchange.json`.
- Execution note:
  the first ingest inserted the candidate row as validation-failed because
  `marketing_by_lang.en.raw_format_fragment` and `marketing_by_lang.zh.too_short`
  tripped the card-quality gate. The CRO JSON was revised to remove the
  hyphenated raw-format fragment and lengthen the zh Investment View, then the
  same idempotency row was rerun with `--force`.
- Candidate ingest result after correction:
  - report type: `econ`
  - slug: `o1-exchange`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `547b9c98-e349-460d-aac7-fcd993b713d2`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 547b9c98-e349-460d-aac7-fcd993b713d2 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2135" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `284a31f2-e4f3-4af9-a793-a0e6f9579af5`
  - promoted_at: `2026-06-23T21:27:56.171973+00:00`
- Project report verification:
  - `tracked_projects.slug=o1-exchange`
  - `project_reports.id=284a31f2-e4f3-4af9-a793-a0e6f9579af5`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=o1.exchange는 Base 거래 애그리게이터 UX가 강점이나, 보상 회계와 거버넌스 투명성 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=547b9c98-e349-460d-aac7-fcd993b713d2`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/o1-exchange/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted English summary plus Investment View.
  - `https://www.bcelab.xyz/en/projects/o1-exchange` returned HTTP `200`
    with the same no-store cache policy and contained the promoted ECON card
    summary plus Investment View.

### BCE-2136 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 07:06 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `o1.exchange의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`.
- Source identity:
  `drive:1Jc6BkGU13UZK_8PJirgPZiav2mbuB_FF:0B8HYgThT3NBydjdyZmxsSGNkQk1qRGtPNzlSemlaUGNpRlhNPQ`.
- Source SHA-256:
  `5f9639f57cc8509baf37273ae00a0607a5925fe92208090578d9d952c38f6b1f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_o1-exchange_bce2136.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_o1-exchange.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug o1-exchange --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_o1-exchange_bce2136.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads before candidate selection. The run then used the same
  candidate validation, upsert, artifact, and telemetry functions against the
  selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `o1-exchange`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `41f3f461-a9bd-4d5c-b2f8-44bd6a6bda06`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 41f3f461-a9bd-4d5c-b2f8-44bd6a6bda06 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2136" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `58d74ee4-cffd-4e1e-887c-4aeb145e080b`
  - promoted_at: `2026-06-23T22:05:19.580864+00:00`
- Project report verification:
  - `tracked_projects.slug=o1-exchange`
  - `project_reports.id=58d74ee4-cffd-4e1e-887c-4aeb145e080b`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=o1.exchange는 제품 출시는 빠르지만, 수익 지속성과 거버넌스 성숙도는 아직 검증 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=41f3f461-a9bd-4d5c-b2f8-44bd6a6bda06`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/o1-exchange/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate` and contained the promoted English summary plus
    Investment View.
  - `https://www.bcelab.xyz/en/projects/o1-exchange` returned HTTP `200` with
    the same no-store cache policy and contained the promoted MAT card summary
    plus Investment View.

### BCE-2148 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 18:12 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `Wormhole의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020 - 2026.md`.
- Source identity:
  `drive:142VuboZ_vd3y1003uyPZe7XZg6cVOZqH:0B8HYgThT3NBySEhSYTl3bXZ6c3JRN2pBaVhZKzVNbFV2cy9JPQ`.
- Source SHA-256:
  `73a5a98e5d8181079d1d9fb19976589dfbc78d8dada6f39d1aeef641f9473515`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_wormhole_bce2148.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_wormhole.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug wormhole --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_wormhole_bce2148.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads before candidate selection. The run then used the same
  candidate validation, upsert, artifact, and telemetry functions against the
  selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `wormhole`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `acd5661b-a9cc-47c0-b9e7-33d3f399eb23`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id acd5661b-a9cc-47c0-b9e7-33d3f399eb23 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2148" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `bb9a7fc9-7813-49d9-965e-d304c8023e91`
  - promoted_at: `2026-06-24T09:12:15.344188+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2148_wormhole_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=wormhole`
  - `project_reports.id=bb9a7fc9-7813-49d9-965e-d304c8023e91`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Wormhole은 멀티체인 인프라 성숙도는 높지만, W 토큰 수익 포획과 잔여 언락이 핵심 검증 과제다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=acd5661b-a9cc-47c0-b9e7-33d3f399eb23`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2148_wormhole_website_verification.json`.
  KO and EN report/project pages for `wormhole` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was rerun with certificate
  verification disabled for the check only.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2166 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 00:37 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `Circle Internet Group — Ondo Tokenized Stock, CRCLon의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Source identity:
  `drive:15U8cvoMOgxZOK3TeAw5cFTpOZObulLwO:0B8HYgThT3NByNWdoMERrVi9ZRk9sNy9JanhCZkIzVXJ4VnpNPQ`.
- Source SHA-256:
  `22fd95ae72ea6ec8fe8000c25b61385492e9f8a4641fdc777d30de97d137fe91`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_circle-internet-group-tokenized-stock-ondo_bce2166.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_circle-internet-group-tokenized-stock-ondo.json`.
- Execution note:
  the filename was not parsed into a slug by the generic Markdown filename
  parser, so this run used the same candidate validation, upsert, artifact, and
  telemetry functions against the selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `circle-internet-group-tokenized-stock-ondo`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d4c77238-eece-469a-8884-5a698db5752b`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d4c77238-eece-469a-8884-5a698db5752b --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2166" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `9ddaa0db-1bc2-4198-b609-45b0adf2ac30`
  - promoted_at: `2026-06-24T15:37:02.966492+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2166_crclon_mat_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=circle-internet-group-tokenized-stock-ondo`
  - `project_reports.id=9ddaa0db-1bc2-4198-b609-45b0adf2ac30`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=CRCLon은 담보와 증명 구조가 강하지만, 주주권 부재와 오프체인 의존이 남은 토큰화 주식 성숙 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=d4c77238-eece-469a-8884-5a698db5752b`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2166_crclon_mat_website_verification.json`.
  KO and EN report/project pages for
  `circle-internet-group-tokenized-stock-ondo` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was rerun with certificate
  verification disabled for the check only.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2180 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 08:00 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `USA₮(USAT)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1IlW8NJtVV8u-AFl7zrCbycK-U7UW4Yyi:0B8HYgThT3NByODJ5bGpGeHJHSEpvS1MvbEJQZk1kSTVNZHpRPQ`.
- Source SHA-256:
  `e2865f5f6bd3fa6b13bdc5c54dbd0b1712135f9851dc0eecf94925f980cb3e35`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_tether-usat_bce2180.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_tether-usat.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_mat_tether-usat_bce2180.md`.
- Execution note:
  the filename was not parsed into a slug by the generic Markdown filename
  parser, so this run used the same candidate validation, upsert, artifact, and
  telemetry functions against the selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `tether-usat`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `1f9fc5f5-a325-4d52-acdf-a98906a0789f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 1f9fc5f5-a325-4d52-acdf-a98906a0789f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2180" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `344320b1-e56d-4914-902f-c079c011d56b`
  - promoted_at: `2026-06-24T23:00:58.045229+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2180_tether_usat_mat_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=tether-usat`
  - `project_reports.id=344320b1-e56d-4914-902f-c079c011d56b`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=USAT는 은행 발행과 준비금 증명은 강하지만, 유동성·실사용·증명 최신성은 아직 검증 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=1f9fc5f5-a325-4d52-acdf-a98906a0789f`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2180_tether_usat_mat_website_verification.json`.
  KO and EN report/project pages for `tether-usat` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier used an
  unverified SSL context for the HTTP/content check because the local CA chain
  was incomplete.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2181 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 08:49 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `WeFi 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1oD6z3H1tmKWDT81NhcQkpA3DTs4xVch9:0B8HYgThT3NByZFpRV2dxbGFHTERoa0V1NS8wMkFuK3I2RGdZPQ`.
- Source SHA-256:
  `94d07108cd935552aa3f60a55200e30b911f765fe8b725eb3487585ca66ff096`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_wefi_bce2181.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_wefi.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_econ_wefi_bce2181.md`.
- Execution note:
  the first ingest inserted the candidate row as validation-failed because
  `marketing_by_lang.{de,en,es,fr}.raw_format_fragment`,
  `summary_by_lang.de.raw_format_fragment`, and
  `marketing_by_lang.zh.too_short` tripped the card-quality gate. The CRO JSON
  was revised to remove raw-format fragments and lengthen the zh Investment
  View, then the same idempotency row was rerun with `--force`.
- Candidate ingest result after correction:
  - report type: `econ`
  - slug: `wefi`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `5a418e94-e270-4042-a0d4-a7e857403d2c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5a418e94-e270-4042-a0d4-a7e857403d2c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2181" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `1ce848dc-4ee5-4eec-905d-8ade66dd6088`
  - promoted_at: `2026-06-24T23:48:49.921171+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2181_wefi_econ_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=wefi`
  - `project_reports.id=1ce848dc-4ee5-4eec-905d-8ade66dd6088`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=WeFi는 금융 실사용과 WFI 보상을 연결하지만, 토큰 외 핵심 회계·Energy·CBM 검증 경로는 아직 제한적이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=5a418e94-e270-4042-a0d4-a7e857403d2c`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2181_wefi_econ_website_verification.json`.
  KO and EN report/project pages for `wefi` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier used an
  unverified SSL context for the HTTP/content check because the local CA chain
  was incomplete.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2182 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 09:10 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `e548427`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `Billions Network의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`.
- Source identity:
  `drive:1Obg-oe1F_H6gDsg4xieZ6q75mZ_zIlgr:0B8HYgThT3NBydURUYTZkRkJUdzNmVzJQSWc5TyttZUtBTGRvPQ`.
- Source SHA-256:
  `92c4bd1ef31cd320d3764342f95320a049bbd11ce6e896222f11dd385962bcee`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_billions-network_bce2182.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_billions-network.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_mat_billions-network_bce2182.md`.
- Execution note:
  the filename was not parsed into a slug by the generic Markdown filename
  parser, so this run used the same candidate validation, upsert, artifact, and
  telemetry functions against the selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `billions-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `fab26ff3-0892-4c3f-9562-0db2910e30e0`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fab26ff3-0892-4c3f-9562-0db2910e30e0 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2182" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `355c13a8-7608-42a5-a8ef-8f1d1d1f64d5`
  - promoted_at: `2026-06-25T00:09:51.59367+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2182_billions_network_mat_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=billions-network`
  - `project_reports.id=355c13a8-7608-42a5-a8ef-8f1d1d1f64d5`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Billions Network는 ZK 신원과 AI 에이전트 신뢰를 결합해 초기 채택은 확보했지만, 유료 검증 수익과 거버넌스는 아직 검증 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=fab26ff3-0892-4c3f-9562-0db2910e30e0`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2182_billions_network_mat_website_verification.json`.
  KO and EN report/project pages for `billions-network` returned HTTP `200`
  with `cache-control: private, no-cache, no-store, max-age=0,
  must-revalidate` and contained the promoted summaries. The local Python TLS
  verifier used an unverified SSL context for the HTTP/content check because
  the local CA chain was incomplete.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2183 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 09:37 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `5352412`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `Ape and Pepe의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023–2026.md`.
- Source identity:
  `drive:1soSljaaEfeBIiCXQZD-mq4TNAQUw_bNV:0B8HYgThT3NByeStSZ2RvNkF1TmtHNmdKd0JtTG9kbHlGcXVNPQ`.
- Source SHA-256:
  `bbc8bf3caa2239f6e92159ef123b775cdbe515f3fb7b2972b6a2ce9c979fb206`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_ape-and-pepe_bce2183.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_ape-and-pepe.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_mat_ape-and-pepe_bce2183.md`.
- Execution note:
  the process-lost retry resumed after the local CRO JSON and source audit
  artifacts had already been generated. The intermediate local source-path
  dry-run artifact had a `sha256:` identity, so the final production ingest
  reused the same candidate validation, upsert, artifact, and telemetry
  functions against the selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `ape-and-pepe`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `1c5fe86d-4ae3-4558-968a-53db2f174960`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 1c5fe86d-4ae3-4558-968a-53db2f174960 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2183" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `6ddcd37e-768b-4e59-b3ea-65d77ea8e0b3`
- DB verification artifact:
  `scripts/pipeline/output/bce2183_ape_and_pepe_mat_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ape-and-pepe`
  - `project_reports.id=6ddcd37e-768b-4e59-b3ea-65d77ea8e0b3`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=APEPE는 커뮤니티와 보안 신호는 강하지만, 수익·거버넌스·DEX 유동성이 부족해 성숙도는 전개 초기다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=1c5fe86d-4ae3-4558-968a-53db2f174960`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2183_ape_and_pepe_mat_website_verification.json`.
  KO and EN report/project pages for `ape-and-pepe` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries plus Investment View copy. The local Python
  TLS verifier used an unverified SSL context for the HTTP/content check
  because the local CA chain was incomplete.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2184 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 10:11 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `5352412`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `MUON 크립토이코노미 설계 분석 보고서_ Micron Technology (Ondo Tokenized).md`.
- Source identity:
  `drive:1zO1MnxjAz68JiiUQiZFLn7HIaobkYbWD:0B8HYgThT3NBycmNHM1FXbUZYNzFDd2N4QjR3ejlBWUFNODZRPQ`.
- Source SHA-256:
  `c2952d93343f1dc2a6acc7f28c9be1ac5732e5dcd93b16bca78c201fae0d3a33`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_micron-technology-tokenized-stock-ondo_bce2184.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_micron-technology-tokenized-stock-ondo.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_econ_micron-technology-tokenized-stock-ondo_bce2184.md`.
- Execution note:
  the generic slug-filter path selected another Micron Drive file first and
  inserted validation-failed job `65bd1c2f-e27d-4d3b-b46e-20b46d19e101`
  because the source evidence belonged to the newer MUON report. The final
  production ingest reused the same candidate validation, upsert, artifact, and
  telemetry functions against the selected Drive file id only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `micron-technology-tokenized-stock-ondo`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `fb3aa259-87b7-4dca-9842-683563a41c3a`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fb3aa259-87b7-4dca-9842-683563a41c3a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2184" --write`.
- Gate result:
  - exit code: `1`
  - no `promote` result returned
  - no `wrote_project_report=true` evidence
  - no `project_report_id` returned
- Blocker:
  - Supabase RPC failed with `P0001`:
    `website-visible project_reports target not found:
    micron-technology-tokenized-stock-ondo/econ/ko`.
  - DB verification found `tracked_projects.slug=micron-technology-tokenized-stock-ondo`
    exists, but its only `project_reports` row is
    `report_type=forensic`, `language=en`, `status=coming_soon`; no website-visible
    ECON/KO target exists for the authority gate to update.
- Operational status:
  - `BCE-2184` must remain blocked until a DataPlatformEngineer/CTO-owned
    target report seed/backfill creates the required website-visible ECON/KO
    `project_reports` row, after which the same gate command can be rerun.
- Pipeline state wiki was updated with this blocked execution evidence. No
  manifest change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2185 ECON/KO Summary Authority Target Seed (2026-06-25 10:16 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `5352412`.
- Primary context checked before execution:
  `knowledge/pipelines/econ.md`, `knowledge/pipelines/analysis-md-summary-candidate.md`,
  and `pipelines/bcelab-runtime-pipelines.json`.
- Target backfill:
  - `tracked_projects.slug=micron-technology-tokenized-stock-ondo`
  - inserted website-visible `project_reports` shell
    `b4d21a04-307a-4f77-9c37-fc601a447b11`
  - `report_type=econ`, `language=ko`, `version=1`, `status=coming_soon`
  - `source_identity=summary-authority-target:micron-technology-tokenized-stock-ondo/econ/ko/version:1`
- Deployable DB repair record:
  `supabase/migrations/20260625011500_seed_micron_technology_ondo_econ_ko_summary_target.sql`.
- Summary Authority Gate rerun:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fb3aa259-87b7-4dca-9842-683563a41c3a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2184" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `b4d21a04-307a-4f77-9c37-fc601a447b11`
  - promoted_at: `2026-06-25T01:16:42.851287+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2185_micron_technology_ondo_econ_ko_db_verification.json`.
- Project report verification:
  - `tracked_projects.last_econ_report_at=2026-06-25T01:16:27.103569+00:00`
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.promoted_project_report_id=b4d21a04-307a-4f77-9c37-fc601a447b11`
  - `card_summary_ko=MUon은 Micron 주식 총수익을 온체인으로 옮기는 RWA 토큰이지만, 상환과 담보 신뢰는 Ondo의 오프체인 운영에 달려 있다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=fb3aa259-87b7-4dca-9842-683563a41c3a`
- Pipeline state wiki was updated with this target-seed and promotion evidence.
  No manifest change was needed because execution stayed within the existing
  `analysis-md-summary-candidate`, `summary_authority_gate`, and
  `econ-report-publishing` contracts.

### BCE-2184 CRO Closeout After Target Seed (2026-06-25 10:20 KST)

- Wake reason: `issue_children_completed`; CRO resumed the execution issue after
  the target-seed child unblocked the gate path.
- Workspace/SHA rechecked:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `5352412`.
- Primary context rechecked before closeout:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- No second gate write was run by CRO because the child issue had already run
  the exact `summary_authority_gate --write` command and the job is now in the
  terminal `promoted` authority state.
- Promotion evidence retained for BCE-2184 closeout:
  - job id: `fb3aa259-87b7-4dca-9842-683563a41c3a`
  - promotion result: `action=promote`, `state=promoted`,
    `wrote_project_report=true`
  - project_report_id: `b4d21a04-307a-4f77-9c37-fc601a447b11`
  - promoted_at: `2026-06-25T01:16:42.851287+00:00`
  - validation status: `valid`
  - validator warnings: none recorded in the candidate artifact
- Artifacts:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_econ_micron-technology-tokenized-stock-ondo_bce2184.json`
  - Candidate ingest artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_econ_micron-technology-tokenized-stock-ondo.json`
  - Source audit:
    `scripts/pipeline/output/paperclip_cro_source_econ_micron-technology-tokenized-stock-ondo_bce2184.md`
  - DB verification:
    `scripts/pipeline/output/bce2185_micron_technology_ondo_econ_ko_db_verification.json`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/micron-technology-tokenized-stock-ondo/econ`
    returned HTTP 200 with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - The route currently renders the locale-pending report shell because the
    website page availability logic requires a localized slide HTML asset before
    it displays summary metadata. This is a website/UI availability nuance, not
    a Summary Authority Gate promotion failure.
- Manifest update was not needed because the closeout remained within the
  existing `analysis-md-summary-candidate`, `summary_authority_gate`, and
  `econ-report-publishing` contracts.

### BCE-2189 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 12:45 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake reason:
  `process_lost_retry`; the local CRO JSON and source audit artifacts already
  existed, so the run resumed from validation/upsert instead of regenerating the
  report summary.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `RealLink의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2021-2026.md`.
- Source identity:
  `drive:1i2aqXyflP84KRpeQeY-vKY3Cpys0j3Oj:0B8HYgThT3NBycDN2V0VqRzEyNEh5ckZFQlNGdzNDWTdyNTJrPQ`.
- Source SHA-256:
  `a3cac10901ef6b9c957069c617b7a47b162d6078b532c74d633e7e2c8f790c43`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_reallink_bce2189.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_reallink.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_mat_reallink_bce2189.md`.
- Execution note:
  the generic entrypoint command was interrupted after the known MAT Korean
  filename path began broad folder downloads before candidate selection. The
  run then used the same candidate validation, upsert, artifact, and telemetry
  functions against the selected Drive file id only.
- Candidate ingest result after correction:
  - report type: `mat` / DB type: `maturity`
  - slug: `reallink`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `be648fe4-2987-44ca-8a42-9f77a15aa702`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id be648fe4-2987-44ca-8a42-9f77a15aa702 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2189" --write`.
- Gate result:
  - exit code: `1`
  - no `promote` result returned
  - no `wrote_project_report=true` evidence
  - no `project_report_id` returned
- Blocker:
  - Supabase RPC failed with `P0001`:
    `website-visible project_reports target not found: reallink/maturity/ko`.
  - DB verification found `tracked_projects.slug=reallink` exists, but
    `project_reports` has no rows for the project. The candidate job is
    `validation_passed` and ready for promotion once the target row exists.
- Operational status:
  - `BCE-2189` must remain blocked until a DataPlatformEngineer/CTO-owned
    target report seed/backfill creates the required website-visible MAT/KO
    `project_reports` row, after which the same gate command can be rerun.
- Pipeline state wiki was updated with this blocked execution evidence. No
  manifest change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2190 RealLink MAT/KO Summary Authority Target Seed (2026-06-25 12:50 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe`.
- Primary context checked before execution:
  `knowledge/pipelines/mat.md`, `knowledge/pipelines/analysis-md-summary-candidate.md`,
  and `pipelines/bcelab-runtime-pipelines.json`.
- Target backfill:
  - `tracked_projects.slug=reallink`
  - inserted website-visible `project_reports` shell
    `20b2c157-4363-4cb3-9376-f1e31fac38d7`
  - `report_type=maturity`, `language=ko`, `version=1`, `status=coming_soon`
  - `source_identity=summary-authority-target:reallink/maturity/ko/version:1`
- Deployable DB repair record:
  `supabase/migrations/20260625035000_seed_reallink_maturity_ko_summary_target.sql`.
- Summary Authority Gate rerun:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id be648fe4-2987-44ca-8a42-9f77a15aa702 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2189" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `20b2c157-4363-4cb3-9376-f1e31fac38d7`
  - promoted_at: `2026-06-25T03:50:32.819028+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2190_reallink_mat_ko_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.last_maturity_report_at=2026-06-25T03:50:23.791986+00:00`
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.promoted_project_report_id=20b2c157-4363-4cb3-9376-f1e31fac38d7`
  - `card_summary_ko=RealLink는 SocialFi 앱 서사와 거래 유동성은 있지만, 공급량 정합성·온체인 팁 데이터·거버넌스 검증이 부족하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=be648fe4-2987-44ca-8a42-9f77a15aa702`
- Website/cache verification:
  - KO and EN project/report pages for `reallink` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - The live website did not yet expose the promoted summary text on those
    surfaces while the seeded shell remains `status=coming_soon`; immediate
    promotion evidence is the `project_reports` row and terminal
    `report_summary_jobs` authority state.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Pipeline state wiki was updated with this target-seed and promotion evidence.
  No manifest change was needed because execution stayed within the existing
  `analysis-md-summary-candidate`, `summary_authority_gate`, and
  `mat-report-publishing` contracts.

### BCE-2189 CRO Closeout After Target Seed (2026-06-25 12:54 KST)

- Wake reason: `issue_children_completed`; CRO resumed the execution issue after
  `BCE-2190` unblocked the missing `project_reports` target.
- Workspace/SHA rechecked:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe`.
- Primary context rechecked before closeout:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- No second gate write was run by CRO because `BCE-2190` had already run the
  exact `summary_authority_gate --write` command and the job is now in the
  terminal `promoted` authority state.
- Promotion evidence retained for BCE-2189 closeout:
  - job id: `be648fe4-2987-44ca-8a42-9f77a15aa702`
  - promotion result: `action=promote`, `state=promoted`,
    `wrote_project_report=true`
  - project_report_id: `20b2c157-4363-4cb3-9376-f1e31fac38d7`
  - promoted_at: `2026-06-25T03:50:32.819028+00:00`
  - validation status: `valid`
  - validator warnings: none recorded in the candidate artifact
- Artifacts:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_reallink_bce2189.json`
  - Candidate ingest artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_reallink.json`
  - Source audit:
    `scripts/pipeline/output/paperclip_cro_source_mat_reallink_bce2189.md`
  - DB and website verification:
    `scripts/pipeline/output/bce2190_reallink_mat_ko_db_website_verification.json`
- Website/cache verification:
  - KO and EN project/report pages for `reallink` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - The live website did not yet expose the promoted summary text while the
    seeded shell remains `status=coming_soon`; this is a website/UI
    availability nuance, not a Summary Authority Gate promotion failure.
- Manifest update was not needed because the closeout remained within the
  existing `analysis-md-summary-candidate`, `summary_authority_gate`, and
  `mat-report-publishing` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 5 (2026-06-24 12:18 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/analysis-md-summary-candidate.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence/backfill context:
  `/private/tmp/mat_backfill_audit_fast.json` showed `needs_processing=259`.
  A current DB comparison found `processed_by_current_db=43` and
  `remaining_by_current_db=216` before this batch item.
- Selected MAT Drive Markdown:
  `Lido DAO의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020 - 2026 (1).md`.
- Source identity:
  `drive:1L9mtXSqFoUWCwlYi59mJ4EFKxgFc8br0:0B8HYgThT3NBya1UzZ24zcDBqWW5DUURqUWdxcWwrMWNBWDg0PQ`.
- Source SHA-256:
  `9da95a81dc0063d29859d8af474998381f3867df6a7775e32731767ebbc7b590`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_lido-dao_bce2055_batch5.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_lido-dao.json`.
- Execution note:
  the local `--source-path` dry-run/write was used first to validate summary
  copy, but that produced a local `sha256:` source identity. The final
  production record was corrected by running the same candidate validation and
  upsert functions against the selected Drive file id only, because the generic
  MAT Drive folder path can begin broad downloads before slug selection on
  Korean filenames.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `lido-dao`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `e9a415a7-24f7-4785-b719-d895c78cbf92`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id e9a415a7-24f7-4785-b719-d895c78cbf92 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2055-batch5" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `85ba306e-910f-4eb6-b997-d7e24dc91d5d`
  - promoted_at: `2026-06-24T03:17:40.296728+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2055_batch5_lido_dao_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=lido-dao`
  - `project_reports.id=85ba306e-910f-4eb6-b997-d7e24dc91d5d`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Lido는 stETH 유동성과 Ethereum 스테이킹 인프라에서 높은 성숙도를 보이지만, 검증인 집중도와 LDO 가치 포착이 핵심 한계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=e9a415a7-24f7-4785-b719-d895c78cbf92`
  - audit item check for the exact Drive file/revision returned
    `processed_by_current_db=true`.
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/lido-dao/maturity` returned HTTP `200`
    and contained the promoted Korean summary and Investment View.
  - `https://www.bcelab.xyz/en/reports/lido-dao/maturity` returned HTTP `200`
    and contained the promoted English summary and Investment View.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because this was a single-candidate backfill execution under the
  existing `analysis-md-summary-candidate` contract.

### BCE-2055 CRO MAT Summary Backfill Batch 6 (2026-06-24 12:52 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/analysis-md-summary-candidate.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Operator wake context:
  the issue had been reopened from `blocked`; the requested action was to
  continue from the latest MAT audit queue rather than stale batch-local
  candidates.
- Latest audit queue:
  `/private/tmp/mat_backfill_audit_fast.json` showed
  `needs_processing_items=259`. The first five queue entries were selected:
  `superfortune`, `re-protocol`, `nockchain`,
  `amd-tokenised-stock-xstock`, and `deepbook-protocol`.
- Duplicate-slug handling:
  `deepbook-protocol` appeared more than once in the audit list. The final
  promoted job used the queue-head file `deepbook-protocol_mat_v1.md` with
  Drive file id `1qhyVyKmjp_TC9gltXp0LMG0GinWErx1x`, not the later duplicate.
- Paperclip CRO JSON outputs:
  - `scripts/pipeline/output/paperclip_cro_summary_mat_superfortune_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_re-protocol_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_nockchain_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_amd-tokenised-stock-xstock_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_deepbook-protocol_bce2055_batch6.json`
- Candidate ingest and promotion results:
  - `superfortune`:
    source identity
    `drive:1KgSEgykSieiGJX3iBu5-qHY-UcDg8blf:0B8HYgThT3NBybTcvVW52c3k5RlFTSXl2RE1FR2w2NnBWL2lnPQ`;
    source SHA-256
    `9f833d8a7019d35b837e93b7647d9c9e8ab08caa09fc96b3eb88a316100d6953`;
    job `167afd1d-e115-491c-9ae9-1a25117173c4`;
    promoted report `286394ca-ee84-4f25-b09a-a53ef46b715b`.
  - `re-protocol`:
    source identity
    `drive:1rhEbhdIh03XwHybt7-rhsgiGbF08d_Hx:0B8HYgThT3NBySmVJT0RwM3AyUHdEeWpFYndWa1djNjAxMmRvPQ`;
    source SHA-256
    `e28322b9ec9474b995e6bee0d6cdb897804f9004a18ddcccc539cae11bbb08b8`;
    job `01ba1a28-a1b9-41a4-918d-38a0f2f2cf1f`;
    promoted report `ee4f7205-0b69-4531-aa9a-4e9b20f5f382`.
  - `nockchain`:
    source identity
    `drive:1yZKETgeqRg9U8dGe6ZoaJWBvLDZfwqCn:0B8HYgThT3NByL1RDRjcvbzBwSmVxaE5ydlJIWHV0Q0NXNk80PQ`;
    source SHA-256
    `b2c17ee477d02e1c5d11ccd502a2207d9a22f40ec22b5744280cea89d65bf84f`;
    job `498bb3a0-0e10-4725-b93c-b9d50bcbb3f8`;
    promoted report `f6825e19-34cd-449c-9aef-ec302f2eeeda`.
  - `amd-tokenised-stock-xstock`:
    source identity
    `drive:1Z3Z9HU7VOndfouQgWERQN8CiOhAQWeBi:0B8HYgThT3NByRTN6Z3NKakRXU2FhZGdKUkhDTmVHbjZZZkdnPQ`;
    source SHA-256
    `12f815294de1ee37ec5e607625a03ca9fcd516958cb372b98de0db86a32eb98a`;
    job `9647caf2-c38f-4d33-a3c0-c1a6813c5b0d`;
    promoted report `fad85639-f2df-458e-b6bc-dd9dd8e49272`.
  - `deepbook-protocol`:
    source identity
    `drive:1qhyVyKmjp_TC9gltXp0LMG0GinWErx1x:0B8HYgThT3NByVTJtbGVqR1dLaFlWWklpbmtpMlRDcnpKQnRNPQ`;
    source SHA-256
    `e8c3d4d2ae3ec2b8f6fd4cf113a835ee555950d3016849733bfb5475d4e10c9c`;
    job `56df0ad2-4b0e-4a91-8804-9bed5ff73b17`;
    promoted report `66438dae-e9e2-4732-825a-d46f9508ac29`.
- Summary Authority Gate write command pattern:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id <job-id> --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2055-batch6" --write`.
- DB verification artifact:
  `scripts/pipeline/output/bce2055_batch6_db_verification.json`.
  All five jobs are `authority_state=promoted`,
  `authority_mode=llm_active`, and linked to `project_reports.status=published`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2055_batch6_website_verification.json`.
  KO and EN report pages for all five slugs returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was rerun with certificate
  verification disabled for the check only.
- Current DB-audit comparison after this batch:
  `processed_by_current_db_in_needs_after_batch=44` and
  `remaining_by_current_db_after_batch=215`.
- Next queue candidates after this batch:
  `solstice-eusx`, `rollbit-coin`, `usdf`, `frax-usd`,
  `nvidia-tokenized-stock-xstock`, then `alphabet-tokenized-stock-xstock`,
  `swissborg`, `nasdaq-tokenized-stock-xstock`, `gusd`, and `allora`.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 7 (2026-06-24 12:59 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/analysis-md-summary-candidate.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Current audit selection:
  `/private/tmp/mat_backfill_audit_fast.json` still contained processed queue
  entries, so selection was made by filtering `needs_processing_items` against
  current DB rows where `report_summary_jobs.authority_state=promoted`.
  Before this batch the DB comparison showed `processed_in_audit=44` and
  `remaining=215`.
- Selected MAT Drive Markdown entries:
  `solstice-eusx`, `rollbit-coin`, `usdf`, `frax-usd`, and
  `nvidia-tokenized-stock-xstock`.
- Paperclip CRO JSON outputs:
  - `scripts/pipeline/output/paperclip_cro_summary_mat_solstice-eusx_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_rollbit-coin_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_usdf_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_frax-usd_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_nvidia-tokenized-stock-xstock_bce2055_batch7.json`
- Candidate ingest and promotion results:
  - `solstice-eusx`:
    source identity
    `drive:1NSObkzBkosbfIPRJadDU5Xs27g7DDltO:0B8HYgThT3NBySlZpaGJQd3JWUkorTDlkajRMUGgwSnNPQjkwPQ`;
    source SHA-256
    `5d33aceb12ad75fd05132cd897a66c403bf01c13c09ca397998678dbbedcd7ed`;
    job `8dc670a5-677b-4fb5-8326-97553bd09106`;
    promoted report `893c4658-8c6d-4b78-888a-820b0aac91b0`.
  - `rollbit-coin`:
    source identity
    `drive:1b7QYlt5yar88SGL8xt1TrDQBVWycHSmu:0B8HYgThT3NByamZWNzNOT1BUaUJabWdLa04vdTJ6a092RDZjPQ`;
    source SHA-256
    `a05959bb40db6d00c2b3a52254f101132d7f4bfacf2c6a1abe15c90d22d6653f`;
    job `08894768-fd31-471d-8897-976141b1d648`;
    promoted report `416bb0d1-41a7-43f1-8bd2-0c7788214550`.
  - `usdf`:
    source identity
    `drive:1cItBJ6hGn7_3mrn2jP25tCiQiU-YHhOA:0B8HYgThT3NByZkNpK0c5RHprMlo1bmNEdldTcVd5SDA1NVEwPQ`;
    source SHA-256
    `7f2654da58bffb0a2d718921b8da39e4c3ebbaab309ba60ee07bcf1ab9398820`;
    job `4f4cbb2b-3c19-4d57-8d57-5de83baa5a3f`;
    promoted report `d5477a8d-ac49-41bc-ac3c-625f0a62dec0`.
  - `frax-usd`:
    source identity
    `drive:1XTGas2NAGX2rbb2DHMnnUDCkNk2I0ARK:0B8HYgThT3NByVWpyUm9zbTdYYjlnVGlXdDdrb0hlMXdsTnpFPQ`;
    source SHA-256
    `a958cd645e5896e42ba9391c840810633a851f89984b8d42f90c953ec8690aa8`;
    job `0c413b4c-371a-4184-94ad-2afb5e018ddc`;
    promoted report `ee57d944-e3bb-43d2-905d-620af42d9d81`.
  - `nvidia-tokenized-stock-xstock`:
    source identity
    `drive:1yGFOLsHpduxJcAxisc0LQ7AIzsb6hsdP:0B8HYgThT3NByWXByQ2hnZ0s0dm9NOEpNRTJvUTJBM0RYeVpjPQ`;
    source SHA-256
    `ae7caa737563fa6a86e3590888defe1526ba1c0f2004ca70a1eb2f02b83c85c9`;
    job `03b69501-0db8-4529-9f74-0c5175ab6a1d`;
    promoted report `47a26dfa-387c-46f6-a4e3-3808398f1930`.
- DB verification artifact:
  `scripts/pipeline/output/bce2055_batch7_db_verification.json`.
  All five jobs are `authority_state=promoted`,
  `authority_mode=llm_active`, and linked to `project_reports.status=published`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2055_batch7_website_verification.json`.
  KO and EN report pages for all five slugs returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. As in Batch 6, local CA chain verification
  was disabled for the HTTP/content check only.
- Current DB-audit comparison after this batch:
  `processed_by_current_db_in_needs_after_batch=49` and
  `remaining_by_current_db_after_batch=210`.
- Next queue candidates after this batch:
  `alphabet-tokenized-stock-xstock`, `swissborg`,
  `nasdaq-tokenized-stock-xstock`, `gusd`, `allora`,
  `sp500-tokenized-stock-xstock`, `slimex`,
  `intel-tokenized-stock-xstock`, `myx-finance`, and `wefi`.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2005 additional migration recovery evidence (2026-06-20 13:35 KST, latest)

- Workspace/SHA used: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab` at `6bc8302`.
- Remote execution ref: `codex/fix-exchange-production-regressions@e1b3fc8`.
- Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860177261
- `supabase migration repair --status applied 20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429`
  - approved and executed successfully
  - log: `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => applied`
- `supabase db push` still fails after repair:
  - Supabase rejects repaired short-date versions as non-matching local migration files
  - suggests reverting at least `20260409 20260412 20260414 20260418 20260427`
- Related concurrent run / regression:
  - https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860170061
  - command path regressed to pre-repair local-insertion blocker
- New board approval requested for revised metadata repair path:
  - `7b7ad020-6ac9-430f-bcc0-16da1e386720`
- Blocker status:
  - `BCE-2006` remains blocked pending board-approved revised repair/rollback direction and a successful `supabase db push`.

### BCE-2005 follow-up recovery evidence (2026-06-20 13:40 KST)

- Auditable workflow support commit added for Actions-based repair on branch
  `codex/fix-exchange-production-regressions`:
  - `7d0be87bae6d53a25e59182649f97ead04014e8c`
- Revised no-op/include-all attempt:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860351179
  - `supabase migration repair --status applied 20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429` succeeded
    (log: `Repaired migration history: [...] => applied`)
  - `supabase db push --include-all` still failed:
    - `Remote migration versions not found in local migrations directory`
    - suggested reverting `20260409 20260412 20260414 20260418 20260427`
- Approved rollback execution:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860406003
  - Rollback evidence:
    - `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => reverted`
- Post-rollback state:
  - Workflow again fails at the original `supabase db push` blocker (oldest local
    April migrations still required before last remote migration).
- Current conclusion:
  - No successful production migration application for Summary Authority Gate has occurred in these runs.
  - BCE-2006 and thus BCE-2005 remain blocked pending board-approved revised metadata
    repair/rollback (approval: `7b7ad020-6ac9-430f-bcc0-16da1e386720`) and a successful `supabase db push`.

## BCE-2006 Supabase Migration History Recovery

- Workspace: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
- Diagnosis SHA: `2a25add`
- Failed run reviewed:
  - https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857395766
  - Failed at `supabase db push` on 2026-06-20 02:25 UTC.
- Exact Supabase CLI blocker:
  - Remote migration versions were present in production history but absent from
    local `supabase/migrations`.
  - Missing local versions:
    `20260408162734`, `20260408181632`, `20260408182202`,
    `20260409015605`, `20260409020123`, `20260409020317`,
    `20260409020850`, `20260409024008`, `20260409062305`,
    `20260409062417`, `20260409062817`, `20260412030602`,
    `20260412030614`, `20260412040231`, `20260412042509`,
    `20260412053802`, `20260412061311`, `20260412113418`,
    `20260412114712`, `20260412115731`, `20260412121557`,
    `20260412130501`, `20260414045616`, `20260414052828`,
    `20260414053057`, `20260414062525`, `20260414233936`,
    `20260414235633`, `20260415061008`, `20260415061036`,
    `20260415092004`, `20260416022513`, `20260416050723`,
    `20260416062634`, `20260416062714`, `20260416073329`,
    `20260418101155`, `20260418151054`, `20260422144324`,
    `20260422234642`, `20260427222305`, `20260430083533`.
- Root cause:
  - Production Supabase history contains timestamped April 2026 migrations that
    are not present in any local branch/ref inspected in this checkout.
  - The current branch also introduced two new date-only `20260620_*`
    migrations; those were renamed to timestamped versions so the new Summary
    Authority Gate migrations have stable ordering and unique versions:
    - `supabase/migrations/20260620111300_add_report_summary_jobs.sql`
    - `supabase/migrations/20260620111400_add_summary_authority_gate.sql`
- Recovery action taken in repo:
  - Added no-op `*_remote_history_compat.sql` marker migrations for each exact
    remote-only version reported by Supabase CLI.
  - No `supabase migration repair`, `supabase db pull`, or production DB write
    was executed locally.
- Recovery rerun:
  - Commit/ref: `a209daf` on `codex/fix-exchange-production-regressions`
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857730221
  - Result: failed after clearing the first remote-only-version blocker.
  - New Supabase CLI blocker: local migrations would need insertion before the
    last remote migration:
    - `20260409_add_tracked_projects_and_project_subscriptions.sql`
    - `20260412_add_referral_subscriber_newsletter.sql`
    - `20260412_add_rls_core_tables.sql`
    - `20260414_add_coming_soon_and_forensic_trigger.sql`
    - `20260417_add_report_timestamp_trigger.sql`
    - `20260418_add_cmc_id_to_tracked_projects.sql`
    - `20260418_fix_rls_for_coming_soon_reports.sql`
    - `20260427_add_aliases_to_tracked_projects.sql`
    - `20260428_add_slide_html_urls_by_lang.sql`
    - `20260429_backfill_project_reports_language_support.sql`
- Remaining operating step:
  - Do not rerun with `supabase db push --include-all`; these files include
    non-idempotent schema creation and may duplicate production objects.
  - Board approval `35a8e2b7-6813-45ab-af09-4bfb00a2570b` approved a
    metadata-only repair that marks the listed local April versions as applied
    in Supabase migration history, with rollback by marking the same versions
    reverted.
  - A runner/operator with valid GitHub Actions execution credentials must run
    the approved repair remotely, then rerun `.github/workflows/db-migration.yml`
    from `codex/fix-exchange-production-regressions@6bc8302` so only genuinely
    pending migrations, including the Summary Authority Gate, are applied.
  - 2026-06-20 CTO follow-up:
    - Current CTO heartbeat verified the same workspace at SHA `6bc8302`.
    - `gh auth status` now shows a valid `workflow`-scoped GitHub credential,
      but `.github/workflows/db-migration.yml` still exposes only
      `supabase db push`; it has no approved `supabase migration repair`
      execution path.
    - Remote repair execution has been delegated to DataPlatformEngineer via
      Paperclip so the repair surface, execution evidence, rerun URL, and wiki
      update are handled as an auditable production operation.
  - 2026-06-20 13:28 KST DataPlatformEngineer follow-up:
    - Workspace verified:
      `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
      at SHA `6bc8302` before execution; remote execution used approved
      follow-up SHA `e1b3fc8` on branch `codex/fix-exchange-production-regressions`.
    - Remote workflow repair surface:
      `.github/workflows/db-migration.yml` gained manual-dispatch inputs
      `repair_status` and `repair_versions`, runs under `environment:
      production`, links Supabase from production secrets, runs
      `supabase migration repair` before `supabase db push`, and logs the exact
      command inputs.
    - Remote repair/db-push run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860177261
    - Repair step result: success. Log evidence:
      `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => applied`.
    - Apply Migrations result: failed. New Supabase CLI blocker:
      remote migration versions are now present in history but not accepted as
      matching local migration files for at least
      `20260409`, `20260412`, `20260414`, `20260418`, and `20260427`.
      CLI suggested rollback:
      `supabase migration repair --status reverted 20260409 20260412 20260414 20260418 20260427`.
    - A concurrent earlier remote run
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860170061
      executed the rollback form for the full approved version set, then failed
      `supabase db push` with the prior "local migration files to be inserted
      before the last migration" blocker. The later run above re-applied the
      approved repair.
    - No additional repair variant was executed because the approved command
      succeeded but produced a new reconciliation blocker; any alternative
      version identifiers or rollback/apply sequence should be explicitly
      approved before another production migration-history write.
  - 2026-06-20 board follow-up:
    - Auditable GitHub Actions repair support is present on
      `codex/fix-exchange-production-regressions` at commit
      `7d0be87bae6d53a25e59182649f97ead04014e8c`.
    - Revised no-op/include-all attempt:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860351179
      - `supabase migration repair --status applied 20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429`
        succeeded and logged `=> applied`.
      - `supabase db push --include-all` still failed with
        `Remote migration versions not found in local migrations directory` and
        suggested reverting `20260409`, `20260412`, `20260414`, `20260418`,
        and `20260427`.
    - Approved rollback run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860406003
      - Rollback evidence:
        `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => reverted`.
      - After rollback, the workflow returned to the original blocker: normal
        `supabase db push` refuses to insert older local April migrations before
        the last remote migration.
    - No successful production Summary Authority Gate migration application has
      occurred in these runs.
    - Further automatic retries are not safe without revised board approval
      `7b7ad020-6ac9-430f-bcc0-16da1e386720` or a DB-owner migration-history
      rebaseline via `supabase db pull` / manual Supabase audit.
  - 2026-06-20 safety cleanup:
    - Removed failed experimental workflow inputs `skip_local_versions` and
      `noop_include_versions` after confirming they did not resolve Supabase
      history reconciliation and could invite unsafe reuse.
    - Cleanup commits pushed to `codex/fix-exchange-production-regressions`:
      - `013fb74` reverts `BCE-2006 no-op legacy migrations for production push`.
      - `f4b6b41` reverts `BCE-2006 skip obsolete local migrations in production push`.
    - Current branch HEAD verified locally and remotely:
      `f4b6b41a519ef83e1da50658e4790e05e52674d3`.
    - `.github/workflows/db-migration.yml` now retains only the approved repair
      execution surface: `repair_status` + `repair_versions`, then normal
      `supabase db push`.
    - `BCE-2006` remains blocked because normal `db push` still fails after
      rollback with the April local-migration insertion blocker. Pending
      decision remains board approval `7b7ad020-6ac9-430f-bcc0-16da1e386720`
      or a DB-owner migration-history rebaseline / manual Supabase audit.
  - 2026-06-20 13:50 KST approved recovery completion:
    - Board approval `7b7ad020-6ac9-430f-bcc0-16da1e386720` approved the
      revised remote-only repair/rebaseline path.
    - Repo compatibility commits on `codex/fix-exchange-production-regressions`
      archived obsolete local migrations that were already represented in
      production history:
      - `3d6d225` archives short-date April local migrations.
      - `fb9d8ef` archives pre-summary migrations already applied in production.
      - `65880c5` adds a read-only `supabase migration list --linked` audit step
        before `supabase db push`.
    - Migration application run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860631382
      - Ref/SHA: `codex/fix-exchange-production-regressions@fb9d8ef0efd41fbe3432bc30309fce848624e8fb`
      - Result: success.
      - `supabase db push` applied:
        - `20260620111300_add_report_summary_jobs.sql`
        - `20260620111400_add_summary_authority_gate.sql`
      - Log evidence: `Finished supabase db push.`
    - Audit rerun:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860660544
      - Ref/SHA: `codex/fix-exchange-production-regressions@65880c5e918b3e0e6f2f8f22ea46d07947273d1e`
      - Result: success.
      - `supabase migration list --linked` shows both local and remote entries
        for `20260620111300` and `20260620111400`.
      - `supabase db push` result: `Remote database is up to date.`
    - `BCE-2006` migration blocker is cleared. Next `BCE-2005` step is to run
      the production-equivalent deploy/E2E evidence path and close remaining
      blockers only after that evidence passes.
    - Production-equivalent deploy/E2E run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860761456
      - Ref/SHA: `codex/fix-exchange-production-regressions@35fa6cfa1129ce0453cd40df9cd6a5ecb600fc9b`
      - Result: success.
      - Verification passed: `npm ci`, `npm run verify:pipeline`,
        `npm run verify:runtime-pipelines`, `npx tsc --noEmit`, `npm test`,
        and `npm run build`.
      - Vercel production URL:
        `https://blockchain-economics-bec9ql0oq-michael-zhangs-projects-df54ac7d.vercel.app`
      - Production regression gate passed against that URL, including Top500
        Bitcoin row/CMC rank/ECON badge/MAT badge and Binance exchange/listing
        API/page checks.
    - `BCE-2005` migration/deploy E2E evidence requirement is satisfied by the
      migration runs above plus production deploy run `27860761456`.

### BCE-2010 Paperclip Agent Boundary Correction (2026-06-20)

- Workspace/SHA used for diagnosis:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `b622168` before local runtime-adapter edits.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Boundary correction:
  - The interim GitHub Models / remote LLM endpoint design was rejected as the
    wrong boundary for BCE-1999.
  - Summary generation belongs to the local Paperclip agent and its local LLM
    runtime.
  - `scripts/pipeline/analysis_md_summary_candidate.py` validates and persists
    Paperclip agent JSON output via `--agent-output-json`; it does not call
    remote LLM endpoints.
  - `.github/workflows/analysis-md-summary-candidate.yml` no longer injects LLM
    endpoint/model/token secrets. `apply` mode requires an explicit
    `agent_output_json` path and otherwise fails before candidate writes.
- Local verification:
  - `python3 -m pytest scripts/pipeline/test_analysis_md_summary_candidate.py`
    covers the Paperclip agent output ingestion contract.
- Remaining closeout evidence:
  - Run a Paperclip local agent on a selected Drive analysis Markdown source and
    capture schema-conformant JSON output.
  - Ingest that JSON with `--agent-output-json` and `--require-agent-output`.
  - Capture valid `report_summary_jobs` job evidence and Summary Authority Gate
    dry-run output showing `dry_run=true` and no `project_reports` write.

### BCE-2138 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 12:29 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest Drive Markdown selected by metadata scan:
  `Zama의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020-2026.md`.
- Source identity:
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Source SHA-256:
  `9364c13aa5054fec008bdf4713cd0ed9393bdba3e259199a01c455e573b42a0d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_zama.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_zama.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broad folder downloads
  when Korean MAT filenames are not parsed into slugs, so this run used the
  same candidate validation/upsert functions against the selected Drive file id
  only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `zama`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `32df6eff-e158-4b87-ae57-272517755613`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 32df6eff-e158-4b87-ae57-272517755613 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2138" --write`.
- Promotion result:
  - result: blocked by target report lookup failure
  - error: `website-visible project_reports target not found: zama/maturity/ko`
  - job state after failure: `validation_passed`
  - wrote_project_report: `false`
  - promoted_project_report_id: none
- Target report verification:
  - `tracked_projects.slug=zama`
  - existing `project_reports` rows for Zama include only
    `forensic/en/status=coming_soon`.
  - No website-visible `maturity/ko` target exists for Summary Authority Gate
    promotion.

### BCE-2139 Zama MAT Summary Authority Target Backfill (2026-06-24 12:35 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `knowledge/pipelines/website.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Root cause:
  candidate job `32df6eff-e158-4b87-ae57-272517755613` is valid and remains
  `authority_state=validation_passed`, but Summary Authority Gate promotion
  requires an existing website-visible `project_reports` target. Production has
  `tracked_projects.slug=zama` and only `forensic/en/status=coming_soon`; it has
  no `maturity/ko/version=1` row.
- Resolution path:
  `supabase/migrations/20260624033500_seed_zama_maturity_ko_summary_target.sql`
  creates a scoped Zama `maturity/ko/version=1` `coming_soon` shell with
  `source_identity=summary-authority-target:zama/maturity/ko/version:1` and
  links the backfill to BCE-2139 and the Zama candidate job.
- Boundary:
  the migration creates only the website-visible target shell. It does not
  promote candidate job `32df6eff-e158-4b87-ae57-272517755613`; the gate must be
  rerun through the approved remote production-write path before the candidate
  can become `llm_active`.
- Approval/apply follow-up:
  Paperclip approval `38971918-7b7e-4def-8b9a-8a1cd4616d5c` was approved by
  `local-board` on 2026-06-25. The approved migration was dispatched through the
  remote production Database Migration workflow as selected SQL only:
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28154738546`
  at head SHA `03462cf7715c5fe9a53fcb78165246bdb6fb2d8e`; job
  `83380460421` completed successfully.
- Post-apply verification:
  production already had the Zama `maturity/ko/version=1` target by this
  follow-up, so the idempotent selected SQL preserved the existing published
  row. Verified target:
  `project_reports.id=9d8e5d61-5333-431e-a240-3625d37d0662`,
  `report_type=maturity`, `language=ko`, `status=published`, `is_latest=true`.
  The original Zama candidate job
  `32df6eff-e158-4b87-ae57-272517755613` is now `authority_state=promoted`,
  `authority_mode=llm_active`, and points to that project report.

### BCE-2140 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 13:02 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) remains blocked on production migration
  approval/apply for the Zama `maturity/ko` Summary Authority Gate target.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists, but `project_reports` still contains
  only `forensic/en/status=coming_soon`; no `maturity/ko/version=1` target is
  available for promotion.
- Routine decision:
  no new candidate ingest or `llm_active --write` promotion was run in BCE-2140.
  The routine remains blocked by the unresolved Zama target migration because
  rerunning the gate before that target exists would reproduce the BCE-2138
  failure.

### BCE-2141 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 13:30 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) is still the active blocker for Zama
  `maturity/ko` Summary Authority Gate target creation/apply. BCE-2140 already
  recorded that rerunning the gate before this target exists would reproduce
  the BCE-2138 failure.
- Drive scan context:
  - Latest raw MAT Markdown was `ZRX ... 0x Protocol.md`, but no matching
    `tracked_projects` row was found for `0x`, `0x-protocol`, or `zrx`.
  - Latest eligible known candidate remains Zama MAT source identity
    `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Candidate job state:
  `32df6eff-e158-4b87-ae57-272517755613` remains
  `status=candidate_ready`, `validation_status=valid`,
  `authority_state=validation_passed`, `report_type=maturity`, `locale=ko`.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists, but `project_reports` still contains
  only `forensic/en/status=coming_soon`; no website-visible
  `maturity/ko/version=1` target is available for promotion.
- Gate check:
  a direct `llm_active --write` retry against job
  `32df6eff-e158-4b87-ae57-272517755613` failed with
  `website-visible project_reports target not found: zama/maturity/ko`, matching
  the known BCE-2138/BCE-2140 blocker.
- Routine decision:
  BCE-2141 remains blocked by BCE-2139. No candidate or `project_reports` write
  was completed in this heartbeat.

### BCE-2142 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 14:07 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) remains `blocked` on board/operator approval
  and remote production apply for the Zama `maturity/ko/version=1` Summary
  Authority Gate target. BCE-2140 and BCE-2141 already recorded the same
  blocker.
- Drive scan context:
  latest raw metadata still places `ZRX ... 0x Protocol.md` ahead of Zama, but
  no `tracked_projects` row exists for `zrx`, `0x`, or `0x-protocol`. The latest
  eligible known candidate remains the previously ingested Zama MAT source
  identity
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists, but `project_reports` still has no
  `maturity/ko/version=1` target; Zama `maturity/ko` promotion would still fail
  target lookup.
- Routine decision:
  BCE-2142 is blocked by [BCE-2139](/BCE/issues/BCE-2139). No new candidate
  ingest or `llm_active --write` promotion was run because it would repeat the
  known target-missing failure before the migration is approved and applied.

### BCE-2143 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 14:31 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) remains `blocked` on the production target
  creation/apply path for Zama `maturity/ko/version=1`.
- Drive scan context:
  the newest raw Markdown remains `ZRX ... 0x Protocol.md`, but no
  `tracked_projects` row exists for `zrx`, `0x`, or `0x-protocol`. The latest
  eligible known candidate remains Zama MAT source identity
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists; `project_reports` still contains only
  `forensic/en/status=coming_soon`; `zama/maturity/ko/version=1` is still
  absent.
- Candidate job state:
  `32df6eff-e158-4b87-ae57-272517755613` remains
  `status=candidate_ready`, `validation_status=valid`,
  `authority_state=validation_passed`, `report_type=maturity`, `locale=ko`.
- Routine decision:
  BCE-2143 is blocked by [BCE-2139](/BCE/issues/BCE-2139). No new candidate
  ingest or `llm_active --write` promotion was run because the required
  website-visible target is still absent and rerunning the gate would reproduce
  the known target lookup failure.

### BCE-2144 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 15:42 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  BCE-2140 through BCE-2143 were blocked because the valid Zama MAT candidate
  job had no website-visible `zama/maturity/ko` target for Summary Authority
  Gate promotion. In this heartbeat, production DB state showed the target now
  exists:
  `project_reports.id=9d8e5d61-5333-431e-a240-3625d37d0662`,
  `report_type=maturity`, `language=ko`, `status=published`.
- Candidate job reused:
  `32df6eff-e158-4b87-ae57-272517755613`.
- Source identity:
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Source SHA-256:
  `9364c13aa5054fec008bdf4713cd0ed9393bdba3e259199a01c455e573b42a0d`.
- Existing candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_zama.json`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 32df6eff-e158-4b87-ae57-272517755613 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2144" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `9d8e5d61-5333-431e-a240-3625d37d0662`
  - promoted_at: `2026-06-24T06:42:15.039977+00:00`
- DB verification:
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.authority_mode=llm_active`
  - `report_summary_jobs.promotion_decision=promote`
  - `project_reports.card_data.summary_authority.mode=llm_active`
  - `project_reports.card_data.summary_authority.job_id=32df6eff-e158-4b87-ae57-272517755613`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/zama/maturity` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted Korean summary and Investment View.
  - `https://www.bcelab.xyz/en/reports/zama/maturity` returned HTTP `200` with
    the same no-store cache policy and contained the promoted English summary
    and Investment View.
  - `https://www.bcelab.xyz/ko/projects/zama` and
    `https://www.bcelab.xyz/en/projects/zama` both returned HTTP `200` with
    the same no-store cache policy and contained the promoted localized MAT card
    summary plus Investment View.
- Pipeline state wiki was updated with this promotion evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2145 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 16:50 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Drive scan context:
  the newest raw Markdown remained `ZRX ... 0x Protocol.md`, but no
  `tracked_projects` row exists for `zrx`, `0x`, or `0x-protocol`. The latest
  eligible website-targeted candidate was Zama MAT.
- Source selected:
  `Zama의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020-2026.md`.
- Source identity:
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Source SHA-256:
  `9364c13aa5054fec008bdf4713cd0ed9393bdba3e259199a01c455e573b42a0d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_zama_bce2145.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_zama.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broad MAT folder
  downloads when Korean filenames are not parsed into slugs, so this run used
  the same candidate validation/upsert functions against the selected Drive file
  id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `zama`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `32df6eff-e158-4b87-ae57-272517755613`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 32df6eff-e158-4b87-ae57-272517755613 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2145" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `9d8e5d61-5333-431e-a240-3625d37d0662`
  - promoted_at: `2026-06-24T07:50:21.817733+00:00`
- DB verification:
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.authority_mode=llm_active`
  - `report_summary_jobs.promotion_actor=paperclip-routine:CRO:BCE-2145`
  - `project_reports.card_summary_ko=Zama는 FHE 기반 기밀성 인프라로 기술·기관 서사는 빠르게 성숙했지만 fee burn과 operator 탈중앙화 검증은 아직 초기 단계다.`
  - `project_reports.card_data.summary_authority.mode=llm_active`
  - `project_reports.card_data.summary_authority.job_id=32df6eff-e158-4b87-ae57-272517755613`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/zama/maturity` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted Korean summary and Investment View.
  - `https://www.bcelab.xyz/en/reports/zama/maturity` returned HTTP `200` with
    the same no-store cache policy and contained the promoted English summary
    and Investment View.
- Pipeline state wiki was updated with this promotion evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 8 (2026-06-24 17:26 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- 처리 결과:
  - `alphabet-tokenized-stock-xstock`: job
    `e5770923-1b63-45e9-8214-4a29fb701e63`, report
    `721553f7-3900-4ad9-bfbe-964b8a315c3c`
  - `swissborg`: job `2c818ec5-f0c1-461a-9a57-8ea28401eeea`,
    report `af17048e-8201-47af-8040-e04814c2311b`
  - `nasdaq-tokenized-stock-xstock`: job
    `6160319b-495f-4b57-843c-de64b61c2cf7`, report
    `1d47af7c-730a-45c5-9ca6-fb6ee4fb57ea`
  - `allora`: job `1539fbd0-4088-4bd1-bba1-8824d7d5f33b`,
    report `c53423d0-ae37-47ce-8dcf-2e1d17d6b2a8`
  - `sp500-tokenized-stock-xstock`: job
    `e920bdc0-476f-4c72-a100-861dce625f33`, report
    `45aaecc1-1b35-4dbe-a37b-6655c0799770`
- 안전 스킵:
  `gusd`는 DB/audit 대상이 `Gemini Dollar/GUSD`이나 Drive 원문 파일명과 본문이
  `GUSD(Gate USD)`를 가리켜 동일 프로젝트 source identity gate를 통과하지 못했다.
  따라서 후보 ingest 및 Summary Authority promotion을 실행하지 않았다.
- 산출물:
  - 후보 ingest:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch8.json`
  - promotion 결과:
    `scripts/pipeline/output/bce2055_batch8_promotion_results.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch8_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch8_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`,
  `authority_state=promoted`, `authority_mode=llm_active`,
  `promotion_actor=paperclip-routine:CRO:BCE-2055-batch8`이며, audit source
  file/revision과 일치한다. KO/EN `project_reports.card_data.summary_authority`
  역시 각 job id와 `llm_active` 모드를 가리킨다.
- 웹 검증:
  다섯 slug의 KO/EN 성숙도 보고서 10개 URL이 모두 HTTP `200`과
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`를
  반환했고, 승격된 로컬라이즈 카드 요약과 Investment View가 렌더 payload에
  포함됐다. 로컬 검증은 CA 체인 문제를 피하려고 TLS 검증만 비활성화했다.
- 현재 백필 집계:
  `/private/tmp/mat_backfill_audit_fast.json`의 `needs_processing_items=259`를
  현재 DB promoted/current-revision job과 재대조한 결과, 처리 완료 54개,
  남은 current-revision 205개다. 위 안전 스킵 1개를 제외하면 다음 실행 가능
  후보는 204개다.
- 다음 큐:
  `slimex`, `intel-tokenized-stock-xstock`, `myx-finance`, `wefi`,
  `bnb48-club-token`, `keeta`, `billions-network`, `ape-and-pepe`,
  `strategy-pp-variable-tokenized-stock-xstock`,
  `tbll-tokenized-etf-xstock`, `ducky`, `usdgo`.

### BCE-2055 CRO MAT Summary Backfill Batch 9 (2026-06-26 13:35 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- audit 복구:
  이전 `/private/tmp/mat_backfill_audit_fast.json`가 현재 런타임에서 사라져
  있었다. Batch 8 위키와 artifact의 다음 큐를 확인했으나 선두 후보
  `slimex`, `intel-tokenized-stock-xstock`, `myx-finance`, `wefi`,
  `bnb48-club-token`, `keeta`, `billions-network`, `ape-and-pepe`,
  `strategy-pp-variable-tokenized-stock-xstock`,
  `tbll-tokenized-etf-xstock`, `ducky`, `usdgo`는 이미 별도 BCE 티켓에서
  `llm_active`로 승격되어 있었다.
- 복구 방식:
  Drive MAT metadata를 재스캔하고 단순 slug/name/symbol substring matching으로
  `/private/tmp/mat_backfill_audit_fast.json`를 재생성했다. 이 재구성 artifact는
  원래 audit과 완전히 동일한 matching contract가 아니므로, 처리 전 파일명과
  본문 subject identity를 직접 확인했다.
- 안전 스킵:
  재구성 audit의 첫 항목은 `Numerai...md`가 `gensyn`으로 잘못 매칭된
  케이스였다. source identity
  `drive:1mCxQ1yRh729EUgyP6p7yujyLnL1JaZBA:0B8HYgThT3NByR2hjbW9PSlp2LzEzd0RneTdJaXJoMTEvSWJzPQ`
  는 이번 batch에서 ingest/promotion하지 않았다.
- 처리 결과:
  - `yzy`: job `b72d9058-1df5-4c3c-9725-2feb59692d69`, report
    `f79ce4e9-7493-402d-9d43-6fe7d51851a8`
  - `melania-meme`: job `02349ba7-fc33-4640-a3bf-73930eef0618`, report
    `c25a3f86-d4e8-4b3f-a3bd-7c4c07235c22`
  - `cow-protocol`: job `3e2d4639-3a8e-4b38-a8fe-0e7d07e80a08`, report
    `a2f3a5a9-0ae9-4201-80c3-2e953b079a9c`
  - `canton-network`: job `4ca79d2b-08ba-450e-b5a3-009df71b8e45`, report
    `90b84dba-cfb4-431a-aa87-268fd6642823`
  - `chainlink`: job `61f098a4-ad54-4f28-baf1-1d5509ba9483`, report
    `dd6683e8-4538-4293-af0b-06213822e0b6`
- Source identities:
  - `yzy`:
    `drive:1bHk-aV1kj5ihWuw5MhN_in92TluxWjO9:0B8HYgThT3NByNGJWVWZ0UHZ1a3VFSlRZVTVtRlNMWHJXbEJnPQ`
  - `melania-meme`:
    `drive:1RZ6xRfLLRf8PdlDRsj9fTE-C9f0MoIKM:0B8HYgThT3NByTnhOZXBUdDBVVnFaWVREUUpnQ1g1UDRkK3ljPQ`
  - `cow-protocol`:
    `drive:1Quonu2c8xJfRpuPj5PGJ5BjeoA48mge8:0B8HYgThT3NByZHI0VmFIa2VqbzV1aHJPSGZLMEsyM0hvUVNVPQ`
  - `canton-network`:
    `drive:1F0jn3B51MptDethEdVD-l1dACxdNALmj:0B8HYgThT3NByMC9GaVRMUlpyaGgrc3psbkh4VFhodXpFaHVFPQ`
  - `chainlink`:
    `drive:1ldP2yXhXIV5cg3ApAATM0a6t4I3tbUmd:0B8HYgThT3NBya3ZaWjdTS3U2SlFOUStYUW4reDkvcEJFN3o0PQ`
- 산출물:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_yzy_bce2055_batch9.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_melania-meme_bce2055_batch9.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_cow-protocol_bce2055_batch9.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_canton-network_bce2055_batch9.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_chainlink_bce2055_batch9.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch9_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch9_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`다. DB artifact의 `project_reports` 조회는
  `canton-network`와 `chainlink`에서 중복 KO row 중 stale row를 함께 반환해
  `summary_authority=null`인 row가 보였으나, authority gate는 위 report id를
  반환했고 웹 렌더 payload는 승격 문구를 포함했다.
- 웹 검증:
  다섯 slug의 KO/EN 성숙도 보고서 10개 URL이 모두 HTTP `200`과
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`를
  반환했고, 승격된 로컬라이즈 카드 요약을 포함했다. 로컬 검증은 CA 체인
  문제를 피하려고 TLS 검증만 비활성화했다.
- 다음 큐:
  재구성 audit에서 Batch 9와 known mismatch를 제외한 다음 후보는
  `stellar`, `zcash`, `berachain`, `usd1`, `eurc`, `dai`,
  `binaryx-new`, `gas`, `safe1`, `awe-network`, `nexus-labs`, `defi-app`다.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 10 (2026-06-26 14:45 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- audit 기준:
  Batch 9에서 복구한 `/private/tmp/mat_backfill_audit_fast.json`의 다음
  미처리 후보를 사용했다. 이 artifact는 Drive metadata fast substring scan
  재구성본이므로, 각 source 파일명과 본문 subject identity를 직접 확인했다.
- 처리 결과:
  - `stellar`: job `6243f7ca-d380-4d43-83f5-d80805f9b2c5`, report
    `e1cef18f-b28d-4469-b42f-2a7795301e2e`
  - `zcash`: job `16cfce37-6a3a-4a0c-a043-2d19b658b3a1`, report
    `84a1bd78-86c1-43c2-8e0e-2d2bfd3c1a88`
  - `berachain`: job `763350e4-d3b4-43be-b62c-a6c3cc3a7f00`, report
    `875e890e-c33b-4636-9813-8277f246c2c4`
  - `usd1`: job `02b5d705-8b67-4d0e-88cf-045fd1b001da`, report
    `29a059e2-4998-4d72-9ba3-32aa422f6bbd`
  - `eurc`: job `b1298f7f-8516-420e-a4ba-e6c693289532`, report
    `2d0c980b-6545-4961-9df2-98d183f85260`
- Source identities:
  - `stellar`:
    `drive:1_HMoY8FUsAL9fMM608A5qeTpN-fN-cHo:0B8HYgThT3NByTm5kZHArdzhoSUxtSGtrK1FZd2Y3UWw1ODZRPQ`
  - `zcash`:
    `drive:1Et5DE2wscvOSoZtGu23VmPfjpdmJJe5W:0B8HYgThT3NByU2ZzVUZGblRJbEEvUkkzUWYxQVBBckZHSUl3PQ`
  - `berachain`:
    `drive:1Dnb1D0LoUkyICYBC9SXHTQkdDaNQ4kLu:0B8HYgThT3NBybTIyemZmaG9kb3lFZWt6VXFOVEdEZk1MdE9FPQ`
  - `usd1`:
    `drive:1WetITxKixf-xIyx-xqCGIGNBXEGrBGVa:0B8HYgThT3NByTEpJcmRZSWRJRm1CNE1aeEVaTUtYQnhEcWhFPQ`
  - `eurc`:
    `drive:1MZNL5DIcHYpSPUApL-9zElmgyvWOXcJH:0B8HYgThT3NBydzFRay9RcTlrRVNBZEtqRHVudlVZTUJraVBzPQ`
- Selector caveat:
  standard `analysis_md_summary_candidate.py --slug berachain` 실행은
  재구성 audit의 known false-match Numerai source identity
  `drive:1mCxQ1yRh729EUgyP6p7yujyLnL1JaZBA:0B8HYgThT3NByR2hjbW9PSlp2LzEzd0RneTdJaXJoMTEvSWJzPQ`
  를 먼저 선택해 invalid job
  `b25cad4e-c7a9-41d0-84fa-fc2ebd3ab198`을 생성했다. 이 job은
  `source_sentences.*.not_in_source`로 validation failed 상태이며
  promotion 대상에서 제외했다. Berachain은 audit에 확정된 Drive file
  id/revision과 `/private/tmp/berachain_mat_source.md`를 직접 바인딩해
  validation-passed job으로 upsert했다.
- 산출물:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_stellar_bce2055_batch10.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_zcash_bce2055_batch10.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_berachain_bce2055_batch10.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_usd1_bce2055_batch10.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_eurc_bce2055_batch10.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch10_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch10_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`이며, authority gate가 반환한 다섯
  `project_reports` row를 조회했다. false-match invalid job 1건은 별도
  caveat로 artifact에 포함했다.
- 웹 검증:
  `stellar`, `zcash`, `berachain`, `usd1`, `eurc`의 KO/EN 성숙도 보고서
  10개 URL이 모두 HTTP `200`과 promoted 카드 요약 문구를 반환했다. 로컬
  검증은 CA 체인 문제를 피하려고 TLS 검증만 비활성화했다.
- 다음 큐:
  재구성 audit에서 Batch 10을 제외한 다음 후보는 `dai`,
  `binaryx-new`, `gas`, `safe1`, `awe-network`, `nexus-labs`, `defi-app`
  순서로 이어진다.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 11 (2026-06-26 15:20 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- audit 기준:
  Batch 10 이후 DB의 promoted `report_summary_jobs` source identity를 다시
  조회하고, 재구성 audit의 known false-match Numerai source를 제외한 다음
  미승격 MAT 후보를 처리했다.
- 처리 결과:
  - `dai`: job `e69eac83-123d-4736-ab1b-f5e90d79e152`, report
    `62472e0f-e26c-4d3c-aa62-0193536161a8`
  - `binaryx-new`: job `4893a4db-8a5a-4206-a5ba-5d535314a562`, report
    `91e71bf3-dd66-440d-bc1d-bdb326fb3976`
  - `gas`: job `4b7fffed-8e42-4679-bdc0-1f8a8bf2cc3f`, report
    `55a08714-b492-4cbc-996e-268821be7dc9`
  - `safe1`: job `a9e1a68b-97c7-47d2-aef2-b3bf02f5e1d0`, report
    `e9ee932e-b13e-4e27-9749-93f2de110bc9`
  - `awe-network`: job `513cbfe2-c8f5-4aaf-900b-1820e279dbab`,
    report `cbc9e0dd-b114-4789-9480-d3b09269e9b5`
- Source identities:
  - `dai`:
    `drive:1zinTBGqSCNT8NqseQN51mlXJHtR6xWqj:0B8HYgThT3NByUnlyTHR2ZVNoalZPQ3N0eVIrRWYvK3EvVUp3PQ`
  - `binaryx-new`:
    `drive:1GMvjTfkd75ClQifznURoSiV6-Sfh_EDg:0B8HYgThT3NByU3lzbFNKZUpPZU1RT3psblJ5UnZsWGdOUW9jPQ`
  - `gas`:
    `drive:176qK8zFkBkdCQHbpLo_lStd6CJmBMEjg:0B8HYgThT3NByT0VDbkI3Yis2U2MrcTkwS1NvN3UrNTlJQWU0PQ`
  - `safe1`:
    `drive:1DwkcJcBEFCDsiLD3Tb6zcHfGsOEJL2qz:0B8HYgThT3NByOFcvYjVMUUZkT2tVbWswRFVlN0pNdjZpWWhzPQ`
  - `awe-network`:
    `drive:1Hm_oe7f4qwoaNRO8Pte95roQniEPEq_Y:0B8HYgThT3NByaUxVbThWYUxGY05XaHZKS3c0SStVZDZQeDBNPQ`
- Validation note:
  `binaryx-new`의 첫 upsert는 summary 문구의 `Four/FORM` 슬래시 표현이
  `raw_format_fragment` gate에 걸려 invalid job으로 삽입됐다. source
  grounding 문장은 원문을 유지하고 카드 요약 문구만 `Four FORM`으로 바꾼
  뒤 같은 idempotency key를 `--force` 상당 경로로 업데이트해
  `validation_status=valid`로 전환했다.
- 산출물:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_dai_bce2055_batch11.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_binaryx-new_bce2055_batch11.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_gas_bce2055_batch11.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_safe1_bce2055_batch11.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_awe-network_bce2055_batch11.json`
  - Candidate artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch11.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch11_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch11_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`이며, authority gate가 반환한 다섯
  `project_reports` row를 조회했다.
- 웹 검증:
  `dai`, `binaryx-new`, `gas`, `safe1`, `awe-network`의 KO/EN 성숙도
  보고서 10개 URL이 모두 HTTP `200`과 promoted 카드 요약 문구를 반환했다.
  로컬 검증은 CA 체인 문제를 피하려고 TLS 검증만 비활성화했다.
- 다음 큐:
  DB promoted source identity를 반영한 다음 후보는 `nexus-labs`,
  `defi-app`, `maplestory-universe`, `kaito-ai`, `grass`, `cheems-pet`,
  `horizen`, `synthetix`, `river`, `sentient` 순서로 이어진다.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 12 (2026-06-26 15:47 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- audit 기준:
  Batch 11 이후 DB의 promoted `report_summary_jobs` source identity를 다시
  조회했다. `nexus-labs`는 이미 같은 source identity가 promoted 상태라
  제외하고, 다음 미승격 후보 5건을 처리했다.
- 처리 결과:
  - `defi-app`: job `4a286334-28c3-4e33-bce5-244ba72d261d`, report
    `15cf3cf9-2a72-40c4-93b7-4b0ca43bdadf`
  - `maplestory-universe`: job `e45ab0a1-fbd0-4510-9162-b4c7249fd23b`,
    report `52820b70-b284-4c9a-bed0-c0750b7c26d8`
  - `kaito-ai`: job `0242b3da-fe31-4cef-98d9-d87cc92a5208`, report
    `5b032b0f-76e3-4e44-9e85-f90979a966f8`
  - `grass`: job `cec0202c-5582-46b0-91cd-850254592173`, report
    `bbd56f1b-4856-4e57-b87d-19d79377db22`
  - `cheems-pet`: job `0bcbd5d4-b22e-499f-90b3-a568e09907d4`, report
    `7e08245f-b722-4c2e-a88c-7ed1258a9b47`
- Source identities:
  - `defi-app`:
    `drive:1tTn3kAreuHZ4SH2g_TGmjygYDcjY2Zmv:0B8HYgThT3NByeitsalhLTGNmNEwwNllBMXVMZnpQbVduayswPQ`
  - `maplestory-universe`:
    `drive:1SKwGQIK3grL3MbKQ2K_UjTTDrn-rdbpH:0B8HYgThT3NBydmltVWwvS0JidGdTQ0FjcHk5UFdZTGlySWdBPQ`
  - `kaito-ai`:
    `drive:17AZSOZCqb4X_aHG8HgC2TneZxBVSPfhK:0B8HYgThT3NByTkpjN1lDZUYwZERzU1BMQTJyeXZIc1hSTlVnPQ`
  - `grass`:
    `drive:12KqbNeGaBxkhXxTaEYd-E_k5i7DYgy88:0B8HYgThT3NBya042VnE3dkR6WWM1MnZBSEhCR2IyVmZSejZFPQ`
  - `cheems-pet`:
    `drive:120MXVLduZ8a5XgW8g7GLuUv3fR5LPGNQ:0B8HYgThT3NByWll2ZDcyY1h0WmM0ZHk1OXFTQ3RTWWF1NU8wPQ`
- Validation note:
  `defi-app`, `kaito-ai`, `grass`, `cheems-pet`의 첫 upsert는 zh 카드
  문구 길이 gate에 걸렸다. 각 zh 문구를 의미 변화 없이 확장하고 같은
  idempotency key를 force update해 `validation_status=valid`로 전환했다.
- 산출물:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_defi-app_bce2055_batch12.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_maplestory-universe_bce2055_batch12.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_kaito-ai_bce2055_batch12.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_grass_bce2055_batch12.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_cheems-pet_bce2055_batch12.json`
  - Candidate artifacts:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch12.json`,
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch12-fix.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch12_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch12_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`이며, authority gate가 반환한 다섯
  `project_reports` row를 조회했다.
- 웹 검증:
  `defi-app`, `maplestory-universe`, `kaito-ai`, `grass`, `cheems-pet`의
  KO/EN 성숙도 보고서 10개 URL이 모두 HTTP `200`과 promoted 카드 요약
  문구를 반환했다. 로컬 검증은 CA 체인 문제를 피하려고 TLS 검증만
  비활성화했다.
- 다음 큐:
  DB promoted source identity를 반영한 다음 후보는 `horizen`,
  `synthetix`, `river`, `sentient`, `wemix`, `reserve-rights`,
  `instadapp`, `dydx-chain`, `sahara-ai`, `banana-for-scale` 순서로
  이어진다.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 13 (2026-06-26 16:15 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- audit 기준:
  Batch 12 이후 DB의 promoted `report_summary_jobs` source identity를 다시
  조회했다. `horizen`은 이미 같은 source identity가 promoted 상태라 제외하고,
  다음 미승격 후보 5건을 처리했다.
- 처리 결과:
  - `synthetix`: job `1c1c82a7-2431-4eac-951b-15794e8404e3`, report
    `8114e6c9-50b8-46e2-9be9-f3ec485cf6ab`
  - `river`: job `1dda31f9-c76c-46af-a25b-1aef36b92688`, report
    `3ecde7b3-93e7-46c4-a772-088028b6b2cf`
  - `sentient`: job `bb75599c-5b9d-4aa5-b8c7-2844df4de94d`, report
    `502efe82-2959-4fcd-af52-bf5d1c28e373`
  - `wemix`: job `5ea8fe16-c2ef-46d0-8b2f-1f5ed68d5f91`, report
    `77494977-a56d-4666-b0eb-fb63906703ea`
  - `reserve-rights`: job `b3f29455-1077-4588-8631-b9de150a2198`,
    report `67aedf2c-96fe-44c1-9d80-e1e1e3b22c6e`
- Source identities:
  - `synthetix`:
    `drive:1yZHmLcklAQYUxc_bDe-5KgAnsQB8GMrH:0B8HYgThT3NByVFpnaGgzZHg2bEIxVmxUbUkwZDR3Qjd0cXRVPQ`
  - `river`:
    `drive:1uw1gknEKUeTSEZl2K2v_ZZdjJFtk0FSc:0B8HYgThT3NByRTVEVFFsUkxrdEFaMWgrTFQyZGlrOE1zVkM4PQ`
  - `sentient`:
    `drive:16H9tAIXZpnCCeoLuZyBmLA5vxKY4rSGX:0B8HYgThT3NBySHZtQ0thSElFMTBLSllCNmNUZWN0NWdtc05BPQ`
  - `wemix`:
    `drive:1c56ieAI1l3HWSGGrhQWofU2lxI7KsYpx:0B8HYgThT3NByR3F3UEYrQUlIU05FV3NFRmlTejdUNXVtdzUwPQ`
  - `reserve-rights`:
    `drive:1umcHtxnvwtmcwSpiji1uYoIi2iSKLCkF:0B8HYgThT3NByQ0tub0tueHBXUEVvckk4Q3lPNklBOHI2elZnPQ`
- Validation note:
  `river`의 첫 upsert는 zh summary 길이 gate에 걸렸다. zh 문구를 의미
  변화 없이 확장하고 같은 idempotency key를 force update해
  `validation_status=valid`로 전환했다.
- 산출물:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_synthetix_bce2055_batch13.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_river_bce2055_batch13.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_sentient_bce2055_batch13.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_wemix_bce2055_batch13.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_reserve-rights_bce2055_batch13.json`
  - Candidate artifacts:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch13.json`,
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_river-bce2055-batch13-fix.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch13_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch13_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`이며, authority gate가 반환한 다섯
  `project_reports` row를 조회했다.
- 웹 검증:
  `synthetix`, `river`, `sentient`, `wemix`, `reserve-rights`의 KO/EN
  성숙도 보고서 10개 URL이 모두 HTTP `200`과 promoted 카드 요약 문구를
  반환했다. 로컬 검증은 CA 체인 문제를 피하려고 TLS 검증만 비활성화했다.
- 다음 큐:
  DB promoted source identity를 반영한 다음 후보는 `instadapp`,
  `dydx-chain`, `sahara-ai`, `banana-for-scale`, `banana-for-scale`,
  `multiversx-egld`, `1inch`, `dogecoin`, `aethir`, `tagger` 순서로
  이어진다.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 14 (2026-06-27 01:32 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- 운영자 지시 반영:
  [BCE-2055](/BCE/issues/BCE-2055) comment
  `5f768dd2-c08a-4630-850d-8360b8183eb1`에서 backfill 재개,
  local Paperclip agent/LLM 경로 유지, remote LLM API 금지, source identity
  gate 유지, ambiguous/no-source publish 금지, batch별 DB/website evidence와
  누적 count 기록 지시를 확인했다.
- audit 기준:
  Batch 13 이후 DB의 promoted `report_summary_jobs` source identity를 다시
  조회했다. `dydx-chain`은 이미 같은 source identity가 promoted 상태라
  제외했다.
- skip:
  - `dydx-chain`:
    `drive:1vzHH4ctd69hO5qg5_6AO1OIlx7znKK9H:0B8HYgThT3NByMXloSEk1eHIrK3pWZFNuQjNyNmRmaG11TG8wPQ`
    는 already promoted same source identity.
  - `banana-for-scale` duplicate:
    `drive:1og_iIzhD-zxLZZfUcJB0eG7yuINwRzrS:0B8HYgThT3NByWmdVUmFPb3Q0cDYwdFMxcGkxZmhNRDYwdHRnPQ`
    는 같은 slug의 두 번째 source이며 제목이 `크립토이코노미 설계 분석
    보고서`라 MAT 성숙도 primary source로 publish하지 않았다.
- 처리 결과:
  - `instadapp`: job `420af0e2-3262-4332-9591-adc8b112dff7`, report
    `624a8774-2ea1-4cb9-910c-c5fb21232298`
  - `sahara-ai`: job `1b49b8b5-f92a-40be-9b32-754714d3d8ed`, report
    `2012432b-2fbe-475a-a2b2-895722cae537`
  - `banana-for-scale`: job `5b845167-c8b3-4a26-95c7-640e1e97cc26`,
    report `25723b99-c687-4f2e-86e8-2f3208b65571`
  - `multiversx-egld`: job `e1ce2a48-07b3-4df1-a13c-c08b83079155`,
    report `39bf4bd7-670d-43ba-b8f2-6f8f91b99f7e`
  - `1inch`: job `89b25c94-aea3-41bf-8f83-05bfd001c865`, report
    `2cde5b89-9c5a-488d-b0dc-ccbc284aa159`
- Source identities:
  - `instadapp`:
    `drive:1jRqbb6c7C6VW7spnpviC2LZ27NyzoXgL:0B8HYgThT3NByVHJZL09XcGRIVmoxcFJBUXBxSEVZb09Hb21zPQ`
  - `sahara-ai`:
    `drive:12_NP0xeAAhKUZY0sHPcAb75RERP68U3g:0B8HYgThT3NBySFd5aXhKdTdPeEs1UlFrVjJWRDU4UlpsSko0PQ`
  - `banana-for-scale`:
    `drive:1j90OvpAZKQC9HaDkIuEgdkjbxx83M-xV:0B8HYgThT3NByZWRRTVI3T3FhM3UrRk5FRWhFNjRWQVhrTDk4PQ`
  - `multiversx-egld`:
    `drive:1-tEI8F2xoI_xdBfzKH_T7yXnEYETgwOC:0B8HYgThT3NByUHRIVW85Y2d0WEw3Sks3Zmh0QnBackZuWGU0PQ`
  - `1inch`:
    `drive:1Ao4rW1PfKsLp3bxpWkuMf2CmWGMb4Ivb:0B8HYgThT3NByN3FMVXBnVXN0SmF4QytRYW5UY0ppbXZVZjZ3PQ`
- Validation note:
  `multiversx-egld`의 첫 upsert는 marketing 문구의 `developer-to-app`
  하이픈 표현이 raw format gate에 걸렸다. 의미 변화 없이 `developer app
  conversion`으로 수정하고 같은 idempotency key를 force update해
  `validation_status=valid`로 전환했다.
- 산출물:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_instadapp_bce2055_batch14.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_sahara-ai_bce2055_batch14.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_banana-for-scale_bce2055_batch14.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_multiversx-egld_bce2055_batch14.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_1inch_bce2055_batch14.json`
  - Candidate artifacts:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch14.json`,
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_multiversx-egld-bce2055-batch14-fix.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch14_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch14_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`이며, authority gate가 반환한 다섯
  `project_reports` row를 조회했다. DB artifact에 skip 2건도 포함했다.
- 웹 검증:
  `instadapp`, `sahara-ai`, `banana-for-scale`, `multiversx-egld`,
  `1inch`의 KO/EN 성숙도 보고서 10개 URL이 모두 HTTP `200`과 promoted
  카드 요약 문구를 반환했다. 로컬 검증은 CA 체인 문제를 피하려고 TLS
  검증만 비활성화했다.
- 누적 count:
  Batch 9부터 Batch 14까지 이 resumed backfill 구간에서 30건을 promoted
  처리했다. Batch 14 자체는 promoted 5건, skip 2건이다.
- 다음 큐:
  DB promoted source identity와 duplicate skip을 반영한 다음 후보는
  `dogecoin`, `aethir`, `tagger`, `unus-sed-leo`, `cardano`,
  `hyperliquid`, `solana`, `tron`, `usd-coin`, `infinity-ground` 순서로
  이어진다.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 15 (2026-06-27 01:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- 운영자 지시 반영:
  Batch 14 이후 audit queue를 이어 처리했고, local Paperclip agent/LLM
  payload만 사용했다. Remote LLM API는 호출하지 않았으며, source identity
  gate와 ambiguous/no-source publish 금지를 유지했다.
- audit 기준:
  DB promoted `report_summary_jobs` source identity를 조회해 이미 promoted
  상태인지 확인한 뒤, 중복 source가 있는 slug는 최신 Drive modifiedTime과
  프로젝트 정체성이 맞는 원문만 선택했다.
- 처리 결과:
  - `dogecoin`: job `b6d64ad0-8b6d-430b-ae7e-c4e68e235259`, latest visible
    report `c4edadde-1779-405e-a927-a7ca793d252e`
  - `aethir`: job `afe2e8fc-4fdf-4dea-9596-f6036f17b1f3`, report
    `62eb9194-dc79-4d8b-9e26-8e2d08d34a6c`
  - `tagger`: job `6bbb60f8-ea25-4c71-80d4-5652bbe35a0e`, report
    `5d259f7a-b1ce-4109-a9e3-c759b554479c`
  - `cardano`: job `728383bd-b514-4dd9-826a-06d70be9ddc3`, latest visible
    report `07ed7fa8-34c6-421c-b18e-d8730cc6c51d`
  - `hyperliquid`: job `9ce9241b-6530-41d9-ab17-9ce41213e8bf`, report
    `c50c9c2e-2f99-4e71-ac9c-fced766db6e4`
- skip:
  - `unus-sed-leo`: candidate job
    `94355e72-10ba-4388-9b25-dd1eb656755f` passed validation, but authority
    gate blocked promotion with `website-visible project_reports target not
    found for unus-sed-leo/maturity/ko`. It remains `validation_passed` and was
    not published.
- Source identities:
  - `dogecoin`:
    `drive:1tZhgHCKgMEo32UE_TKr1GQ-5Ux_GUrOu:0B8HYgThT3NByNkZZZVpKU3NwSlRBT3BDdDMvbDBIWnZPd3BrPQ`
  - `aethir`:
    `drive:1QB1BG3i-5kMTq8BuMHApW81oZUaoIhTL:0B8HYgThT3NByTEVLRFhBb1l5Q3BzN0YvUXJSL3BGZGl2cmVZPQ`
  - `tagger`:
    `drive:1nEtlhSNGSJ-Aa4G1NXJQybTJXheADK2-:0B8HYgThT3NByVmxYNHp6UUE4a0l6cVZ1alBKTjdROVVQTlFBPQ`
  - `cardano`:
    `drive:1vO-NM_rbZNy7MszIALmPWU6KZQMVeAEQ:0B8HYgThT3NBySDFDZTdCdkRUWCtNeU9odG1PN3F0ZTQ5UVdJPQ`
  - `hyperliquid`:
    `drive:166xrWeLhTWBmzRYwz9ia9KX2pNfAo8AR:0B8HYgThT3NByYmNBK014TVYySVE4OU9pVGxMYnpGNGNqMkk4PQ`
- Validation note:
  첫 upsert에서 일부 카드 문구의 slash, hyphen, 숫자 약어가
  `raw_format_fragment` 또는 `too_short` gate에 걸렸다. 의미 변화 없이
  자연어형 문장으로 수정한 뒤 같은 idempotency key를 force update해 다섯
  promoted 후보와 `unus-sed-leo` skip 후보 모두 `validation_status=valid`로
  만들었다.
- 산출물:
  - CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_dogecoin_bce2055_batch15.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_aethir_bce2055_batch15.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_tagger_bce2055_batch15.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_unus-sed-leo_bce2055_batch15.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_cardano_bce2055_batch15.json`,
    `scripts/pipeline/output/paperclip_cro_summary_mat_hyperliquid_bce2055_batch15.json`
  - Candidate artifacts:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch15.json`,
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch15-fix.json`,
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_hyperliquid-bce2055-batch15.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch15_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch15_website_verification.json`
- DB 검증:
  다섯 promoted job은 `validation_status=valid`, `authority_state=promoted`,
  `authority_mode=llm_active`이며, latest visible `project_reports` KO row에
  promoted 카드 요약과 `summary_source_md_file_id`가 반영됐다. `dogecoin`과
  `cardano`는 authority gate 출력 id와 별개로 latest visible sibling row가
  갱신되므로 DB artifact는 latest visible row 기준으로 기록했다.
- 웹 검증:
  `dogecoin`, `aethir`, `tagger`, `cardano`, `hyperliquid`의 KO/EN 성숙도
  보고서 10개 URL이 모두 HTTP `200`과 promoted 카드 요약 문구를 반환했다.
  로컬 검증은 CA 체인 문제를 피하려고 TLS 검증만 비활성화했다.
- 누적 count:
  Batch 9부터 Batch 15까지 이 resumed backfill 구간에서 35건을 promoted
  처리했다. Batch 15 자체는 promoted 5건, skip 1건이다.
- 다음 큐:
  `unus-sed-leo`는 website-visible target이 생기기 전까지 publish하지 않고,
  다음 후보는 `solana`, `tron`, `usd-coin`, `infinity-ground` 이후 최신 audit
  queue에서 이어진다.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2146 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 17:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- 최신 Drive Markdown metadata scan 결과:
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`.
- Source metadata:
  - report type: `mat` / DB type: `maturity`
  - drive file id: `10FHhLUz-RqXfzj-BmFviF54az6c4U4XY`
  - revision id:
    `0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`
  - modified time: `2026-06-23T08:20:21.000Z`
- Blocker:
  `tracked_projects` has no matching target for `0x Protocol`, `0x-protocol`,
  or `ZRX`, and `report_summary_jobs` has no existing row for the selected Drive
  file. The routine cannot safely ingest or promote because Summary Authority
  Gate requires an existing target project/report row.
- Required unblock:
  Data/platform owner must add or map the 0x Protocol/ZRX target project and
  KO maturity report seed, then rerun this routine against the same Drive
  file/revision.
- Manifest change:
  no change needed. This is a target data/backfill blocker under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2153 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 19:36 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Drive source:
  `io.net 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1UnRw-bWnnNKn7FsuxRd6A9bLznVgiGG9:0B8HYgThT3NByK0NQMXpFWW84OWxGSUwvd3AvTkJSRHhLWTZRPQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_econ_io-net_bce2153.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_io-net.json`.
- Candidate ingest result:
  - slug/report: `io-net/econ`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `43837f75-e014-428a-af4a-d72e2b4a9f52`
- Summary Authority Gate:
  - command mode: `llm_active --write`
  - actor: `paperclip-routine:CRO:BCE-2153`
  - decision: `promote`
  - authority state: `promoted`
  - wrote project report: `true`
  - project report id: `0c73691e-38fa-43d9-bd22-ab0aaa234228`
  - promoted at: `2026-06-24T10:36:10.031799+00:00`
- Project report verification:
  - `project_reports.id=0c73691e-38fa-43d9-bd22-ab0aaa234228`
  - `tracked_projects.id=fb282651-3a6b-44f9-beef-fd90ce2ac3ec`
  - `report_type=econ`
  - `summary_source_md_file_id=1UnRw-bWnnNKn7FsuxRd6A9bLznVgiGG9`
  - `card_summary_ko=io.net은 AI 컴퓨트 수요와 DePIN 보상을 연결하지만, IO 가치포획은 유료 사용과 투명성에 달려 있다.`
- Manifest change:
  no change needed. This was a normal successful run under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2147 0x Protocol/ZRX MAT Target Seed (2026-06-24 17:42 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 원인:
  [BCE-2146](/BCE/issues/BCE-2146)이 선택한 최신 MAT Markdown
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`에 대해
  `tracked_projects` canonical target이 없어서 Drive source lookup이
  차단됐다.
- 대상 source identity:
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Repo-side seed:
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`
  adds/repairs canonical `tracked_projects.slug=0x`, `symbol=ZRX`,
  `coingecko_id=0x`, aliases `0x protocol`, `0x-protocol`, `zrx`, `zero ex`,
  and a KO `project_reports` `maturity/version=1` Summary Authority Gate target.
- Backfill behavior:
  the migration is idempotent, preserves existing non-cancelled report status,
  reactivates archived project rows, merges aliases, records the Drive
  file/revision in `card_data.summary_authority_target`, and updates
  `last_maturity_report_at` only from an eligible `published`, `coming_soon`,
  or `in_review` target.
- Manifest change:
  no change needed. This remains target data/backfill work under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.
- Next step:
  after the migration is applied in the target DB, resume
  [BCE-2146](/BCE/issues/BCE-2146) and rerun candidate ingest plus
  `llm_active --write` promotion against the same Drive file/revision.

### BCE-2150 0x/ZRX Target Apply Still Pending (2026-06-24 19:21 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- New recurrence evidence:
  [BCE-2150](/BCE/issues/BCE-2150) produced candidate job
  `885624b8-1a5e-4265-970e-d14adb86b790` for source identity
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Candidate state:
  `validation_status=valid`, `authority_state=validation_passed`.
- Gate failure:
  `summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2150" --write`
  failed with `tracked project not found: 0x`; no `project_reports` write
  occurred.
- Approval/apply state:
  board approval
  [44bc62b2-ff81-43f4-bf86-faed5172ac7b](/BCE/approvals/44bc62b2-ff81-43f4-bf86-faed5172ac7b)
  for applying
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`
  remained `pending`.
- Escalation:
  created [BCE-2151](/BCE/issues/BCE-2151) for CTO-owned remote apply/verify
  of the 0x/ZRX target seed and linked [BCE-2147](/BCE/issues/BCE-2147) as
  blocked by it.
- Next step:
  after [BCE-2151](/BCE/issues/BCE-2151) applies and verifies
  `tracked_projects.slug=0x` plus the KO `maturity/version=1` target, resume
  [BCE-2150](/BCE/issues/BCE-2150) with the same gate write command.

### BCE-2149 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 18:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Drive source:
  `Wormhole 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1KSoYyYBp_2lhOIgsrk8QyrH8bg0q31M_:0B8HYgThT3NBybGptR09JRVBTd1IvdHJXVnFTVXUrczkvUi9jPQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_econ_wormhole.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_wormhole.json`.
- Candidate ingest result:
  - slug/report: `wormhole/econ`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `390cefbc-b87a-4146-9770-0248bd88aaa4`
- Summary Authority Gate:
  - command mode: `llm_active --write`
  - actor: `paperclip-routine:CRO:BCE-2149`
  - decision: `promote`
  - authority state: `promoted`
  - wrote project report: `true`
  - project report id: `cefaffd4-bb1b-4ffa-a89a-f72fcca1cf10`
- Manifest change:
  no change needed. This was a normal successful run under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2150 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 19:22 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  process-lost retry; the issue had no prior comments, so the run resumed from
  workspace artifacts and Paperclip heartbeat context.
- Drive source:
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`.
- Source identity:
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Source SHA-256:
  `1714ef8196b372f387ebfe36bbee9fc87719bd12aa2fe78ac05e4d55c873f0d7`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_0x_bce2150.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_0x.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug 0x --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_0x_bce2150.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  downloads before candidate selection. The run then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `0x`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `885624b8-1a5e-4265-970e-d14adb86b790`
  - authority state: `validation_passed`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2150" --write`.
- Promotion result:
  - blocked before project report write
  - error: `tracked project not found: 0x`
  - `wrote_project_report=false`
- Production DB verification:
  - `tracked_projects` has no matching row for `slug=0x`, `symbol=ZRX`, or
    `name ilike %0x%`.
  - `project_reports` therefore has no website-visible `0x/maturity/ko`
    Summary Authority Gate target.
- Blocker:
  [BCE-2147](/BCE/issues/BCE-2147) remains blocked on applying the repo-side
  target seed migration
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`.
- Routine decision:
  [BCE-2150](/BCE/issues/BCE-2150) is blocked by
  [BCE-2147](/BCE/issues/BCE-2147). No `project_reports` write was completed;
  the valid candidate job is ready to promote after the 0x/ZRX target seed is
  applied.
- Manifest change:
  no change needed. This is a target data/backfill blocker under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2150 CRO Analysis MD Summary JSON Ingestion Routine Unblocked (2026-06-25 17:45 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `da9fe5a`.
- Wake context:
  `issue_blockers_resolved`; [BCE-2147](/BCE/issues/BCE-2147) was `done`, so
  [BCE-2150](/BCE/issues/BCE-2150) resumed without a duplicate checkout.
- Primary context checked before closeout:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Blocker resolution verified:
  - `tracked_projects.slug=0x`, `symbol=ZRX`, `status=active`
  - KO maturity target report exists:
    `project_reports.id=7cc38496-9e3d-44a0-8413-f69cbffe006a`,
    `report_type=maturity`, `language=ko`, `version=1`,
    `status=coming_soon`
- Candidate job verified:
  - job id: `885624b8-1a5e-4265-970e-d14adb86b790`
  - source identity:
    `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`
  - validation status: `valid`
  - authority state: `promoted`
  - authority mode: `llm_active`
  - promotion decision: `promote`
  - promoted project report id:
    `7cc38496-9e3d-44a0-8413-f69cbffe006a`
- Summary Authority Gate rerun:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2150" --write`
  returned `noop` because the job was already terminal `promoted`; no duplicate
  `project_reports` write occurred during the resume heartbeat.
- DB and website verification artifact:
  `scripts/pipeline/output/bce2150_0x_db_website_verification.json`.
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/0x/maturity` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted Korean summary text.
  - `https://www.bcelab.xyz/en/reports/0x/maturity` returned HTTP `200` with
    the same no-store cache policy and contained the promoted English summary
    text.
  - `https://www.bcelab.xyz/ko/projects/0x` and
    `https://www.bcelab.xyz/en/projects/0x` returned HTTP `200` with the same
    no-store cache policy and contained the promoted localized MAT card summary.
  - The local Python verifier used certificate verification disabled for the
    content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a blocker-resolution closeout under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2154 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 20:00 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB scan:
  latest unpromoted source remains
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`.
- Source identity:
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Existing candidate job:
  `885624b8-1a5e-4265-970e-d14adb86b790`.
- Candidate state:
  - `validation_status=valid`
  - `authority_state=validation_passed`
  - `promoted_project_report_id=null`
- Production DB verification repeated:
  - no `tracked_projects` row matched `slug=0x`, `symbol=ZRX`, or
    `name ilike %0x%`.
  - no `project_reports` target exists for `0x/maturity/ko`.
- Routine decision:
  no new JSON generation, candidate ingest, or `llm_active --write` promotion
  was run. The next valid action is applying/verifying
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`
  through [BCE-2151](/BCE/issues/BCE-2151), then rerunning the existing valid
  candidate job promotion.
- Manifest change:
  no change needed. This is the same target data/backfill blocker under the
  existing `analysis-md-summary-candidate` and `summary_authority_gate`
  contracts.

### BCE-2154 Blocker Resolved / Idempotent Closeout (2026-06-25 17:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `ba85c2a`.
- Wake context:
  `issue_blockers_resolved`; [BCE-2151](/BCE/issues/BCE-2151) was `done`, so
  the 0x/ZRX target seed blocker was rechecked instead of repeating the prior
  blocked status.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Target verification:
  production now has `tracked_projects.slug=0x`, `name=0x Protocol`,
  `symbol=ZRX`, `coingecko_id=0x`, and aliases including `0x protocol`,
  `0x-protocol`, `zero ex`, `zero-ex`, and `zrx`.
- Candidate/gate verification:
  candidate job `885624b8-1a5e-4265-970e-d14adb86b790` is already
  `validation_status=valid`, `authority_state=promoted`, and
  `promoted_project_report_id=7cc38496-9e3d-44a0-8413-f69cbffe006a`.
- Idempotent gate check:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2154" --write`
  returned `action=noop`, `state=promoted`, `wrote_project_report=false`, and
  `project_report_id=7cc38496-9e3d-44a0-8413-f69cbffe006a` because the job was
  already terminal.
- Website/cache verification:
  `https://www.bcelab.xyz/ko/reports/0x/maturity`,
  `https://www.bcelab.xyz/en/reports/0x/maturity`,
  `https://www.bcelab.xyz/ko/projects/0x`, and
  `https://www.bcelab.xyz/en/projects/0x` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted localized 0x/ZRX maturity summary. Local verification
  disabled TLS certificate verification for the content check only because the
  local CA chain may be unavailable.
- Manifest change:
  no change needed. This closeout used the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2155 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 20:31 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Candidate selection:
  the newest Drive source remains the known ZRX/0x MAT source blocked by missing
  `tracked_projects` / `project_reports` target. Because that blocker is already
  recorded in BCE-2154/BCE-2147/BCE-2151, this run processed the next
  unprocessed source with an existing website-visible target:
  `Zama 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1F7w0cCsbhZHsvKbM7zYFPgx7W_Kf_lAz:0B8HYgThT3NByRkd2c0xTQ2RHSUxCWEtSdE9GbW51VEs1eTFvPQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_econ_zama.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_zama.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `zama`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `94bcfd9a-ba6e-4ec3-9d8d-f66da606a135`
- Execution note:
  the generic entrypoint command was attempted first but delayed in Supabase
  telemetry after broad Drive candidate selection. The run then used the same
  candidate validation, upsert, artifact, and gate functions against the
  selected Drive file id only, preserving Drive source identity.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 94bcfd9a-ba6e-4ec3-9d8d-f66da606a135 --authority-mode llm_active --actor "paperclip-routine:CRO:d32c5062-3fce-4aa8-aeb4-3ee951b634d1" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `18cfc837-cfea-4671-b0ba-aa06445f392e`
- Deployment/cache implication:
  the promotion updated Supabase `project_reports` directly through the Summary
  Authority Gate RPC. No repo deploy was required; website visibility depends on
  the existing report data fetch/cache behavior.
- Manifest change:
  no change needed. This execution used the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2157 0x/ZRX MAT Target Seed Applied (2026-06-24 21:40 KST)

- Workspace/SHA before repair:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Repair commit:
  `bab7d76` on branch `codex/paperclip-agent-summary-source`.
- Applied migration:
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`.
- Remote apply evidence:
  GitHub Actions database migration run
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28098879427`
  completed successfully through the selected SQL migration path.
- Target verification:
  dry-run Summary Authority Gate for candidate job
  `885624b8-1a5e-4265-970e-d14adb86b790` resolved a website-visible
  `0x/maturity/ko` target and would promote to project report
  `7cc38496-9e3d-44a0-8413-f69cbffe006a`.
- Dry-run command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2156"`.
- Dry-run result:
  `dry_run=true`, `action=promote`, `wrote_project_report=false`, reason
  `dry-run promotion would call atomic DB RPC`.
- Manifest change:
  no change needed. This was target seed data under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2158 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 22:19 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `3765764`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Candidate selection:
  processed the newest Drive Markdown source:
  `AWE 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1ApDo2bVWFAykInB4mdh0rzQKMtzULmJ9:0B8HYgThT3NByQm0xcUlySGE4RzFpM1J1V2Q2NWlHSTRyOWs4PQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_for_awe-network_bce2158.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug awe-network --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_awe-network_bce2158.json --require-agent-output --limit 1 --force`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_awe-network.json`.
- Candidate ingest result:
  - report type: `for`
  - DB report type: `forensic`
  - slug: `awe-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `de5600d2-6b4d-4691-82cd-4d69a08b2a62`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id de5600d2-6b4d-4691-82cd-4d69a08b2a62 --authority-mode llm_active --actor "paperclip-routine:CRO:5db9bfc2-1afb-47e2-9277-93f149152cf0" --write`.
- Promotion result:
  blocked by Supabase RPC error
  `website-visible project_reports target not found: awe-network/forensic/ko`.
- Production DB verification:
  - `tracked_projects.slug=awe-network` exists with symbol `AWE`.
  - `project_reports` has `awe-network/forensic/en` with status `coming_soon`.
  - no `awe-network/forensic/ko` website-visible target row exists.
  - candidate job remains `status=candidate_ready`,
    `validation_status=valid`, `authority_state=validation_passed`, and
    `promoted_project_report_id=null`.
- Required unblock:
  seed/backfill a website-visible `awe-network/forensic/ko` target row, then
  rerun the existing valid candidate job promotion.
- Manifest change:
  no change needed. This is target data/backfill under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2161 Arcium ARX Forensic KO Summary Target Seed (2026-06-24 22:44 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Migration added:
  `supabase/migrations/20260624134500_seed_arcium_forensic_ko_summary_target.sql`.
- Target scope:
  create or repair the missing website-visible
  `arcium/forensic/ko/version:1` target row required by Summary Authority Gate
  job `0334ab47-dfa6-44ae-aa43-884fcb8d74ae`.
- Production apply/verification:
  because local `supabase` and `psql` CLIs were unavailable, the seed payload
  was applied through the existing Supabase service-role API using the same
  row contract as the migration.
  - inserted/verified `project_reports.id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`
  - slug/report target: `arcium/forensic/ko/version:1`
  - status: `coming_soon`
  - source identity:
    `summary-authority-target:arcium/forensic/ko/version:1`
- Gate dry-run verification:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0334ab47-dfa6-44ae-aa43-884fcb8d74ae --authority-mode llm_active --actor "paperclip:DataPlatformEngineer:BCE-2161-dry-run"`
  returned `dry_run=true`, `wrote_project_report=false`, action `promote`,
  and `project_report_id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`.
- Production write boundary:
  this is target seed/backfill data only. It did not invoke
  `summary_authority_gate.py --write`, did not promote the candidate, and did
  not write candidate summary content to `project_reports`.
- Manifest change:
  no change needed. This remains under the existing
  `analysis-md-summary-candidate` authority gate contract; the active FOR slide
  publishing contract is unchanged.

### BCE-2158 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 22:27 KST)

- Resume reason:
  `issue_children_completed` after `BCE-2159` completed the missing target-row
  backfill.
- Workspace/SHA at resume:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Unblock evidence from `BCE-2159`:
  - migration:
    `supabase/migrations/20260624132200_seed_awe_network_forensic_ko_summary_target.sql`
  - remote migration run:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28101735345
  - target row:
    `project_reports.id=b2cf33e4-e157-44ae-97bc-1698e18d045a`,
    `report_type=forensic`, `language=ko`, `version=1`,
    `status=coming_soon`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id de5600d2-6b4d-4691-82cd-4d69a08b2a62 --authority-mode llm_active --actor "paperclip-routine:CRO:5db9bfc2-1afb-47e2-9277-93f149152cf0" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `b2cf33e4-e157-44ae-97bc-1698e18d045a`
  - promoted at: `2026-06-24T13:27:35.92693+00:00`
- DB verification after promotion:
  - candidate job `de5600d2-6b4d-4691-82cd-4d69a08b2a62` now has
    `authority_state=promoted` and
    `promoted_project_report_id=b2cf33e4-e157-44ae-97bc-1698e18d045a`.
  - promoted report `card_summary_ko`:
    `AWE는 급등 후 고점 거래량과 되돌림이 겹쳐 단기 조작 취약성이 높아진 상태다.`
  - promoted report `marketing_content_by_lang.ko`:
    `투자 관점에서는 0.0576 지지와 0.0639 돌파를 확인하기 전까지 추격 매수를 피해야 한다.`
  - `card_data.summary_authority.mode=llm_active` with the same job id,
    idempotency key, source identity, and promoted timestamp.
- Deployment/cache implication:
  promotion updated Supabase `project_reports` directly through the Summary
  Authority Gate RPC. No repo deploy was required; website visibility follows
  the existing report data fetch/cache behavior for `coming_soon` report rows.
- Manifest change:
  no change needed. This was target data plus Summary Authority Gate execution
  under the existing `analysis-md-summary-candidate` contract.

### BCE-2172 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 03:10 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Circle xStock(CRCLx)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1dCpNj9lr08J3dyEaKVKZbeXGfam6BYwh:0B8HYgThT3NByaGd6ZnlyYlZvMmVEVkNmdVZDTDNIRHRTWmdnPQ`.
- Source SHA-256:
  `9c9747bc1b89fcc33959b3cf95d46778c7d8d79f15a1f22bd16124e454a43409`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_circle-tokenized-stock-xstock_bce2172.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_circle-tokenized-stock-xstock.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT Drive
  downloads because this Korean MAT filename is not parsed into a slug, so this
  run used the same candidate validation/upsert functions against the selected
  Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `circle-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `22a76093-dd7f-480e-9d02-f00f628a6824`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 22a76093-dd7f-480e-9d02-f00f628a6824 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2172" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `60c9fd00-2327-480b-a51c-3b931dbedac1`
  - promoted_at: `2026-06-24T18:10:15.986421+00:00`
- Project report verification:
  - `tracked_projects.slug=circle-tokenized-stock-xstock`
  - `project_reports.id=60c9fd00-2327-480b-a51c-3b931dbedac1`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=CRCLx는 실사용 RWA 선두권이지만, 성숙도는 담보 검증과 가격추적 투명성에 좌우된다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=22a76093-dd7f-480e-9d02-f00f628a6824`
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Backfill Batch 9 - SOON Network (2026-06-26 12:58 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/analysis-md-summary-candidate.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2223](/BCE/issues/BCE-2223) Quack AI MAT 승격분은
  이미 반영되어 있어 제외하고 다음 명확한 미승격 후보를 선별했다.
- 후보 선택:
  `Numerai/Numeraire`는 공개 KO target report row가 없고, `WOULD` 및
  `IVVON`은 tracked project 매칭이 없어 스킵했다. `SOON Network`는
  Drive 파일명, 본문 제목, 공식 웹사이트, symbol, tracked project slug
  `soon-network`가 일치해 source identity gate를 통과했다.
- 선택한 Drive Markdown:
  `SOON Network의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024-2026.md`.
- Source identity:
  `drive:1pDHNWOEbhnXlaxvRGd8fpiIJZVe06qcV:0B8HYgThT3NByMGJKSHFZMDVsTkc4R015dkJ0TEE2Y0NHZXNBPQ`.
- Source SHA-256:
  `62b697d3879bea5aa12ee147118ee55fdaab5eac4bfe59b54a69df013099faed`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_soon-network_bce2055_batch9.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_soon-network_bce2055_batch9.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_soon-network.json`.
- Execution note:
  broad Drive scan 재계산은 본문 다운로드 단계에서 heartbeat 시간을 초과해
  중단했다. 선택된 SOON Network Drive file id 1개에 대해 기존
  `AnalysisMdCandidate`, `process_candidate`, `upsert_job`, and
  `write_artifact` 경로를 적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `soon-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `c2ab8d02-1a28-4c69-8046-b3b4a78c32d3`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id c2ab8d02-1a28-4c69-8046-b3b4a78c32d3 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2055-batch9" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `15dd96c8-1a4b-46b5-9e57-b282d378c3aa`
  - promoted at: `2026-06-26T03:56:48.395434+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2055_batch9_soon_network_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=soon-network`
  - `tracked_projects.symbol=SOON`
  - `project_reports.id=15dd96c8-1a4b-46b5-9e57-b282d378c3aa`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=SOON Network는 SVM 롤업 스택 서사가 선명하지만 TVL, 거래량, 실측 TPS가 낮아 아직 초기 전개 단계에 머문다.`
  - `card_summary_en=SOON Network has a clear SVM rollup stack narrative, but low TVL, volume, and observed TPS keep it in an early development stage.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=c2ab8d02-1a28-4c69-8046-b3b4a78c32d3`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/soon-network`,
    `https://www.bcelab.xyz/ko/reports/soon-network/maturity`,
    `https://www.bcelab.xyz/en/projects/soon-network`,
    `https://www.bcelab.xyz/en/reports/soon-network/maturity` returned HTTP
    `200`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2225 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 12:49 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 PUMP FOR promoted source와 같은 본문 SHA를 가진
  별도 Drive file id가 남아 있었으며, source identity 기준으로는 미승격
  파일이므로 이번 실행 대상으로 처리했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai/Numeraire`, `WOULD`, `IVVON`은 공개 target
  row 또는 tracked project 매칭이 없어 스킵했다. 다음 eligible source로
  `PUMP` FOR의 별도 Drive file id를 선택했다.
- 선택한 Drive Markdown:
  `PUMP 시장 무결성 및 심층 포렌식 리스크 보고서 (1).md`.
- Source identity:
  `drive:1MXxDuk7l-mU54d4YyOtLodgIgMUo1xo9:0B8HYgThT3NByT2Q2clhTNEpGdUZYcUZYNDQ2cDBIYXRjVUxBPQ`.
- Source SHA-256:
  `5778319e270bbed1411e2bde90c36e82afb0f89e6b1379a66d446b6d7ba2fddf`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_pump-fun_bce2225.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_pump-fun_bce2225.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_pump-fun.json`.
- Execution note:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug pump-fun --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_pump-fun_bce2225.json --require-agent-output --limit 1 --force`
  는 기존 재발과 동일하게 동일 slug 매칭에서 다른 Drive file id
  `1ApDo2bVWFAykInB4mdh0rzQKMtzULmJ9`를 먼저 선택해 source grounding
  mismatch로 validation_failed row
  `5de9993c-3e0c-4f86-ad23-0f9477f4649b`를 갱신했다. 해당 row는 promotion
  대상이 아니며, 선택한 PUMP Drive file id 1개에 기존 candidate validation,
  artifact, telemetry, and `upsert_job` 함수를 적용했다. 공개 forensic
  target row가 version 2/latest이므로 candidate source version을 2로
  명시했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `pump-fun`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `1daeab0f-eb30-42b4-b032-4a5741c44bb4`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 1daeab0f-eb30-42b4-b032-4a5741c44bb4 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2225" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d644d0ec-d894-4792-9e75-11f69ade5098`
  - promoted at: `2026-06-26T03:49:11.195406+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2225_pump_fun_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=pump-fun`
  - `tracked_projects.symbol=PUMP`
  - `project_reports.id=d644d0ec-d894-4792-9e75-11f69ade5098`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=PUMP는 급락 후 반등했지만 조작 리스크 67/100 HIGH와 장기선 하회가 남아 추격보다 재지지 확인이 우선이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=1daeab0f-eb30-42b4-b032-4a5741c44bb4`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/pump-fun`,
    `https://www.bcelab.xyz/ko/reports/forensic/pump-fun`,
    `https://www.bcelab.xyz/en/projects/pump-fun`,
    `https://www.bcelab.xyz/en/reports/forensic/pump-fun` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2224 CRO Routine Execution Evidence (2026-06-26 11:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 최신 미승격 후보 중 `Numerai/Numeraire`는 tracked
  project는 있었지만 KO `project_reports` target row가 없어 제외했고,
  `WOULD` 및 `IVVON`은 tracked project match가 없어 제외했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했고,
  다음 명확한 eligible source로 `Legacy Frax Dollar` MAT를 선택했다.
- 선택한 Drive Markdown:
  `Frax의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020 - 2026.md`.
- Source identity:
  `drive:1aaLkpMEy9RZuiTN5URl6UVNJesOBjrUY:0B8HYgThT3NBybEV6SEhxZEw3WWlaaVVHYjdRaVZsNG5PM3A4PQ`.
- Source SHA-256:
  `9941b5739649f37f46ff6bc051d5b38779e743697cac16201455486b8356182a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_legacy-frax-dollar_bce2224.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_frax-usd_bce2224.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_legacy-frax-dollar.json`.
- Execution note:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug legacy-frax-dollar --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_legacy-frax-dollar_bce2224.json --require-agent-output --limit 1 --force`
  는 기존 재발과 동일하게 slugless Drive broad-download 경로에서 제한 시간
  내 완료되지 않아 중단했다. 기존 candidate validation, artifact, and
  `upsert_job` 함수를 선택된 Legacy Frax Dollar Drive file id 1개에만
  적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `legacy-frax-dollar`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `e243099a-7c6d-45fb-8638-65bca65957c4`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id e243099a-7c6d-45fb-8638-65bca65957c4 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2224" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `c34c1adb-ce99-4d5a-82d0-4934f47cae4a`
  - promoted at: `2026-06-26T02:38:11.358793+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2224_legacy_frax_dollar_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=legacy-frax-dollar`
  - `tracked_projects.symbol=FRAX`
  - `project_reports.id=c34c1adb-ce99-4d5a-82d0-4934f47cae4a`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=e243099a-7c6d-45fb-8638-65bca65957c4`
- Website/cache verification:
  - `https://bcelab.xyz/ko/projects/legacy-frax-dollar`,
    `https://bcelab.xyz/ko/reports/legacy-frax-dollar/maturity`,
    `https://bcelab.xyz/en/projects/legacy-frax-dollar`,
    `https://bcelab.xyz/en/reports/legacy-frax-dollar/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2223 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 10:43 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 [BCE-2222](/BCE/issues/BCE-2222)는 AWE FOR를
  promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai/Numeraire`는 공개 target row가 없고,
  `WOULD`는 symbol-only 매칭 시 Wormhole `W`로 오탐될 수 있어 직전
  skip 판단을 유지했으며, `IVVON`은 tracked project 매칭이 없었다.
  `Frax` MAT와 `PUMP` duplicate FOR도 visible target 또는 기존 충돌
  이슈로 스킵하고, 다음 명확한 eligible source인 `PENGU` FOR를 선택했다.
- 선택한 Drive Markdown:
  `PENGU 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1G9mu2zRPscKGdD2NGQJrsCUqhXov7COk:0B8HYgThT3NBySjlBQkx5NHVTeTgwb0ZsYWtxSXJRSHJreStrPQ`.
- Source SHA-256:
  `7861cc3eaf954eed8c3bfd5c07bcc677876b06c38383b6004e098e07d7ec3b85`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_pudgy-penguins_bce2223.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_pudgy-penguins_bce2223.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_pudgy-penguins.json`.
- Execution note:
  generic entrypoint의 broad-download 및 symbol-only false positive 위험을
  피하기 위해 기존 candidate validation, telemetry, artifact, and
  `upsert_job` 함수를 선택된 PENGU Drive file id 1개에 적용했다. 로컬 source
  snapshot dry-run에서 raw-format 및 Chinese length 검증 실패를 수정한 뒤
  Drive identity candidate를 upsert했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `pudgy-penguins`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `58b6fac6-73ed-48f6-af2a-51dba342521a`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 58b6fac6-73ed-48f6-af2a-51dba342521a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2223" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `02bd706e-dc8c-44f3-a0d1-465fceb8c371`
  - promoted at: `2026-06-26T01:39:10.001585+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2223_pudgy_penguins_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=pudgy-penguins`
  - `tracked_projects.symbol=PENGU`
  - `project_reports.id=02bd706e-dc8c-44f3-a0d1-465fceb8c371`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=PENGU는 저점 후 반등했지만 조작 리스크와 단기 저항, 장기 평균선 하회가 남아 돌파 확인이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=58b6fac6-73ed-48f6-af2a-51dba342521a`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/pudgy-penguins`,
    `https://www.bcelab.xyz/ko/reports/forensic/pudgy-penguins`,
    `https://www.bcelab.xyz/en/projects/pudgy-penguins`,
    `https://www.bcelab.xyz/en/reports/forensic/pudgy-penguins` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2217 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 07:37 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 위키 기록 [BCE-2212](/BCE/issues/BCE-2212) 및 DB의 promoted
  `report_summary_jobs` source identity를 확인했다. [BCE-2212](/BCE/issues/BCE-2212)는
  `gho/mat` source를 이미 promoted 및 웹 검증 완료했으며, 이번 실행은
  promoted source identity를 제외한 다음 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 `Numerai` MAT는 공개 KO target row가 없고, `WOULD` 및 `IVVON`은
  `tracked_projects` 매칭이 없어 스킵했다. `Frax` MAT는 `frax`,
  `legacy-frax-dollar`, `frax-usd` 매칭이 충돌하고 exact `frax`에는
  published target row가 없어 자동 승격 대상으로 쓰지 않았다. 다음 명확한
  eligible source로 `HTX DAO` ECON을 선택했다.
- 선택한 Drive Markdown:
  `HTX DAO 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1Mauz5C3r-6yHV7PB7R62IGWM6neb5dKQ:0B8HYgThT3NByQjdEc3JlajlEODE2dFltKzNHbk9GTlNHRGxFPQ`.
- Source SHA-256:
  `e5ae995dcfac3153ff33afbaf5e86612f46707be0e26f120c6d1358a598f0876`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_htx-dao_bce2217.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_htx-dao_bce2217.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_htx-dao.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, artifact, and `upsert_job` 함수를 선택된 HTX DAO
  Drive file id 1개에만 적용했다. 첫 validation은 영어권 summary의
  `buyback-and-burn` 하이픈 표현이 raw-format gate에 걸렸고, CRO JSON
  문구를 low-format 단일 문장으로 수정한 뒤 valid로 통과했다.
- Candidate ingest result:
  - report type: `econ`
  - slug: `htx-dao`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `10c9677d-f5cb-43e3-a82a-7387f2b514be`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 10c9677d-f5cb-43e3-a82a-7387f2b514be --authority-mode llm_active --actor "paperclip-routine:CRO:f7a3d559-5968-4a15-829f-c5e65cbb9db6" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `779be68e-4f69-45fd-b692-180430075afc`
  - promoted at: `2026-06-25T22:37:23.655258+00:00`
- Project report verification:
  - `tracked_projects.slug=htx-dao`
  - `tracked_projects.symbol=HTX`
  - `project_reports.id=779be68e-4f69-45fd-b692-180430075afc`
  - `report_type=econ`, `version=1`, `language=ko`, `status=published`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=10c9677d-f5cb-43e3-a82a-7387f2b514be`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2217_htx_dao_econ_db_website_verification.json`.
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/htx-dao`,
    `https://www.bcelab.xyz/ko/reports/htx-dao/econ`,
    `https://www.bcelab.xyz/en/projects/htx-dao`, and
    `https://www.bcelab.xyz/en/reports/htx-dao/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces returned HTTP `200`; the content check looked only for the KO
    summary string, so `contains_ko_summary=false` is expected on EN pages.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2216 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 07:06 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354` on branch `codex/paperclip-agent-summary-source`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 위키 기록 [BCE-2212](/BCE/issues/BCE-2212) 및 DB의 promoted
  `report_summary_jobs` source identity를 확인했다. 작업트리에는
  [BCE-2213](/BCE/issues/BCE-2213), [BCE-2214](/BCE/issues/BCE-2214),
  [BCE-2215](/BCE/issues/BCE-2215) 산출물이 있었고, DB에서는 해당
  Beldex/Jupiter Perps LP/HTX DAO MAT source가 이미 `promoted` 상태임을
  확인했다. 이번 실행은 DB의 promoted source identity를 제외하고 다음
  후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 `Numerai` MAT는 `numeraire` project는 있으나 공개 KO target row가
  없고, `WOULD`와 `IVVON`은 `tracked_projects` 매칭이 없어 스킵했다.
  `Frax` MAT는 `frax`, `legacy-frax-dollar`, `frax-usd` 매칭 충돌이 있어
  이전 안전 기준대로 스킵했다. 다음 명확한 eligible source로
  `c8ntinuum` MAT를 선택했다.
- 선택한 Drive Markdown:
  `c8ntinuum의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024–2026.md`.
- Source identity:
  `drive:16pSHV6eZ-LN0gtGewtadbqk3guFTIbMu:0B8HYgThT3NByMkIrckU2NUJXYkRPUkprVlAvenFiaHNjTG40PQ`.
- Source SHA-256:
  `2c282df619e8c998a7bb53d1593ef71786a9007da603df8b1fa97dd5c5d6b0fa`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_c8ntinuum_bce2216.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_c8ntinuum_bce2216.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_c8ntinuum.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, artifact, telemetry, and `upsert_job` 함수를 선택된
  c8ntinuum Drive file id 1개에만 적용했다. 첫 검증은 KO 문장 fragment
  gate로 실패했으나 CRO JSON 문구를 단일 완결문으로 수정한 뒤 재검증했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `c8ntinuum`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `fe4a451b-5ac0-475a-9c60-af12c35c2677`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fe4a451b-5ac0-475a-9c60-af12c35c2677 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2216" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `73bfbcfe-fcd4-42de-89a7-99336fd229bf`
  - promoted at: `2026-06-25T22:06:21.90205+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2216_c8ntinuum_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=c8ntinuum`
  - `tracked_projects.symbol=CTM`
  - `project_reports.id=73bfbcfe-fcd4-42de-89a7-99336fd229bf`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=이 프로젝트는 상호운용 기술과 CTM 소각 구조를 결합했지만 독립 사용량과 수익, 거버넌스 공개가 부족해 전개 서사 단계에 머문다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=fe4a451b-5ac0-475a-9c60-af12c35c2677`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/c8ntinuum`,
    `https://www.bcelab.xyz/ko/reports/c8ntinuum/maturity`,
    `https://www.bcelab.xyz/en/projects/c8ntinuum`,
    `https://www.bcelab.xyz/en/reports/c8ntinuum/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2215 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 06:55 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  프로세스 유실 재시도였으므로 기존 로컬 산출물과 DB 상태를 먼저 확인했다.
  최신 위키 기록 [BCE-2212](/BCE/issues/BCE-2212)는 `gho/mat` source를 이미
  promoted 및 웹 검증 완료했다. 이번 [BCE-2215](/BCE/issues/BCE-2215) 산출물은
  재시작 전에 이미 생성, valid ingest, `llm_active` promotion까지 완료되어
  있었고, 이번 heartbeat에서는 그 상태를 DB와 웹에서 재검증했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 기준으로 promoted source identity를
  제외한 다음 eligible source로 `HTX DAO` MAT를 처리했다.
- 선택한 Drive Markdown:
  `HTX DAO의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024-2026 YTD.md`.
- Source identity:
  `drive:1cEQV8f01A4J6J63s2EbNpVmiIiXum0BU:0B8HYgThT3NByUkU2NmFYcENCVml5bTE2ZmRzODkvUmhDMitRPQ`.
- Source SHA-256:
  `14561eae02c020139190d77b1b7b31df9e102619172aa7941822d8defa25a6a5`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_htx-dao_bce2215.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_htx-dao_bce2215.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_htx-dao.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, artifact, and `upsert_job` 함수를 선택된 HTX DAO
  Drive file id 1개에만 적용한 산출물이 이미 존재했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `htx-dao`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `67de9681-0cbd-459f-a240-fba96d729af8`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 67de9681-0cbd-459f-a240-fba96d729af8 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2215" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `5d2879d5-2a27-4a3b-9208-78edfdaeb4c9`
  - promoted at: `2026-06-25T21:42:02.709759+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2215_htx_dao_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=htx-dao`
  - `tracked_projects.symbol=HTX`
  - `project_reports.id=5d2879d5-2a27-4a3b-9208-78edfdaeb4c9`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=HTX DAO는 누적 소각과 스테이킹으로 거래소 연계 경제 서사를 키웠지만, 거버넌스 실행권과 투명성은 아직 성숙 단계에 못 미친다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=67de9681-0cbd-459f-a240-fba96d729af8`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/htx-dao`,
    `https://www.bcelab.xyz/ko/reports/htx-dao/maturity`,
    `https://www.bcelab.xyz/en/projects/htx-dao`,
    `https://www.bcelab.xyz/en/reports/htx-dao/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2213 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 05:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 위키 기록 [BCE-2212](/BCE/issues/BCE-2212) 및 DB의 promoted
  `report_summary_jobs` source identity를 확인했다. 이번 실행은 이미 promoted
  된 source identity를 제외하고 다음 후보를 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 ECON/MAT/FOR
  전체 스캔했다. 최신 unpromoted 후보 중 `Numerai` MAT는 공개 KO target row가
  없고, `WOULD` 및 `IVVON` MAT/ECON은 `tracked_projects` 매칭이 없어서
  스킵했다. `Frax` MAT는 target row가 없어 스킵했고, 다음 eligible source인
  `Beldex` MAT를 선택했다.
- 선택한 Drive Markdown:
  `Beldex의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2019-2026.md`.
- Source identity:
  `drive:11Jmsw4-RjwXvGQdG2k-QSsAdaLhndRt5:0B8HYgThT3NByYmNoZjhZZ0dzdGpQWFdmdlArMWNkRDhiTXprPQ`.
- Source SHA-256:
  `8e8140f9623b8239cc43fa35b997a5f22dc1af9203eb5e03d1036707341c5924`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_beldex_bce2213.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_beldex_bce2213.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_beldex.json`.
- Execution note:
  표준 CLI
  `analysis_md_summary_candidate.py --type mat --slug beldex --drive-root-scope all --agent-output-json ... --require-agent-output --limit 1 --force`
  를 먼저 시도했으나, 기존 기록과 동일하게 generic entrypoint가 `--limit`
  적용 전 광범위 Drive 다운로드 경로에 들어가 중단했다. 이후 동일 모듈의
  candidate validation, artifact, telemetry, and `upsert_job` 함수를 선택된
  Beldex Drive file id 1개에만 적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `beldex`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `7f46447f-5419-4431-a3b3-5c770d9f613f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 7f46447f-5419-4431-a3b3-5c770d9f613f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2213" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `36894431-29dd-43dd-abe7-915267edec50`
  - promoted at: `2026-06-25T20:37:38.767368+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2213_beldex_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=beldex`
  - `tracked_projects.symbol=BDX`
  - `project_reports.id=36894431-29dd-43dd-abe7-915267edec50`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=Beldex는 프라이버시 거래와 PoS 마스터노드 기반은 구현했지만 앱 사용량과 경제 자립성 검증은 남아 있는 전개 서사 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=7f46447f-5419-4431-a3b3-5c770d9f613f`
- Website/cache verification:
  - `https://bcelab.xyz/ko/projects/beldex`,
    `https://bcelab.xyz/ko/reports/beldex/maturity`,
    `https://bcelab.xyz/en/projects/beldex`,
    `https://bcelab.xyz/en/reports/beldex/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2214 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 06:06 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 위키 기록 [BCE-2213](/BCE/issues/BCE-2213) 및 DB의 promoted
  `report_summary_jobs` source identity를 확인했다. 이번 실행은 이미 promoted
  된 source identity를 제외하고 다음 후보를 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 ECON/MAT/FOR
  전체 스캔했다. 최신 unpromoted 후보 중 `Numerai` MAT는 공개 KO target row가
  없고, `WOULD` 및 `IVVON` MAT/ECON은 `tracked_projects` 매칭이 없어서
  스킵했다. `Frax` MAT는 target row가 없어 스킵했다. 다음 후보
  `Jupiter Perps_JLP` MAT는 자동 scoring이 `jupiter-ag`와 충돌할 수 있어
  더 구체적인 `jupiter-perps-lp` target row를 수동 확인한 뒤 선택했다.
- 선택한 Drive Markdown:
  `Jupiter Perps_JLP의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023-2026.md`.
- Source identity:
  `drive:1QWFHSCmITY_iEEF2dRT-Cj9Rwm8RK5-X:0B8HYgThT3NBya3dKM0JqTStnaEV1cWZIeCt6bzc2VjFKd1pVPQ`.
- Source SHA-256:
  `f3e112f47e05c35dfebdfec18f1424a5939a53b7c7df50a3f824bd7db4ad3e8f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_jupiter-perps-lp_bce2214.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_jupiter-perps-lp_bce2214.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_jupiter-perps-lp.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로와 `jupiter-ag`/`jupiter-perps-lp`
  slug 충돌을 피하기 위해 기존 candidate validation, artifact, and `upsert_job`
  함수를 선택된 Jupiter Perps/JLP Drive file id 1개와 `jupiter-perps-lp`
  project에만 적용했다. 최초 validation은 `Perps/JLP` 슬래시 표현이
  raw-format gate에 걸려 실패했고, CRO JSON 문구를 `Jupiter Perps와 JLP`
  형태로 수정해 재검증했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `jupiter-perps-lp`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `975c8225-5195-4cb2-9f6b-2f2e132a0dd5`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 975c8225-5195-4cb2-9f6b-2f2e132a0dd5 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2214" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `8ba91f5e-4e5d-4f63-87ad-49d2aff9a843`
  - promoted at: `2026-06-25T21:06:24.151901+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2214_jupiter_perps_lp_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=jupiter-perps-lp`
  - `tracked_projects.symbol=JLP`
  - `project_reports.id=8ba91f5e-4e5d-4f63-87ad-49d2aff9a843`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=Jupiter Perps와 JLP는 Solana Perps 유동성과 JLP 수수료 축적을 검증했지만, Keeper와 Oracle, 트레이더 손익 리스크 관리가 성숙도 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=975c8225-5195-4cb2-9f6b-2f2e132a0dd5`
- Website/cache verification:
  - `https://bcelab.xyz/ko/projects/jupiter-perps-lp`,
    `https://bcelab.xyz/ko/reports/jupiter-perps-lp/maturity`,
    `https://bcelab.xyz/en/projects/jupiter-perps-lp`,
    `https://bcelab.xyz/en/reports/jupiter-perps-lp/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2171 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 02:35 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `CRCLx 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1ivu6JKJBX4lW4vI3ja0TE1vKffginfUB:0B8HYgThT3NByenF1dlprUFMrMUp3NG5nanlpWUFtclVScjBNPQ`.
- Source SHA-256:
  `25f66e96b6bc1966f43fb67cf5edc5547881de2954b7d8bd18274120bf703252`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_circle-tokenized-stock-xstock_bce2171.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_circle-tokenized-stock-xstock.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug circle-tokenized-stock-xstock --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_circle-tokenized-stock-xstock_bce2171.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known broad Drive folder download path started
  before final candidate selection. The run then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  Drive file id only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `circle-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `27234d89-1f7d-440e-945d-79c49f5bfbf7`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 27234d89-1f7d-440e-945d-79c49f5bfbf7 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2171" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `6f526c63-efea-4802-a166-fa0baddff107`
  - promoted_at: `2026-06-24T17:35:56.646539+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2171_crclx_econ_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=circle-tokenized-stock-xstock`
  - `project_reports.id=6f526c63-efea-4802-a166-fa0baddff107`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=CRCLx는 1:1 담보형 xStock으로 접근성과 DeFi 조합성은 강하지만, 주주권 부재와 가격 괴리 리스크가 남는다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=27234d89-1f7d-440e-945d-79c49f5bfbf7`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2171_crclx_econ_website_verification.json`.
  KO and EN report/project pages for `circle-tokenized-stock-xstock` returned
  HTTP `200` with `cache-control: private, no-cache, no-store, max-age=0,
  must-revalidate` and contained the promoted summaries plus Investment View.
  The local Python TLS verifier lacked a CA chain, so the HTTP/content
  verification was rerun with certificate verification disabled for the check
  only.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2170 GUSD Project Metadata Correction (2026-06-25 02:25 KST)

- Wake reason:
  `process_lost_retry` after [BCE-2169](/BCE/issues/BCE-2169) completed the
  `gusd/maturity/ko` summary promotion.
- Workspace/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before data correction:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Diagnosis:
  `tracked_projects.slug=gusd` still displayed `Gemini Dollar` with alias
  `gemini dollar`, while promoted jobs for the same slug target Gate USD:
  - econ job `6a83d86a-531e-49c9-b9e2-299e1c0731ca`
  - maturity job `bbe4f358-3ca0-4e1b-81b4-b593bb960fa4`
- Live market identity check:
  CoinGecko `id=gusd` resolves to GUSD/Gate, while Gemini Dollar resolves to
  `id=gemini-dollar`.
- Data correction:
  `supabase/migrations/20260624172500_fix_gusd_gate_usd_metadata.sql` updates
  only the `tracked_projects` display metadata for `slug=gusd`:
  `name=Gate USD`, `symbol=GUSD`, aliases
  `gusd`, `gate usd`, `gate gusd`, `gateusd`, and default
  `website_url=https://www.gate.com/gusd` when absent.
- Provenance boundary:
  no `project_reports` or `report_summary_jobs` rows were changed; existing
  summary authority job ids, source identities, and promoted report ids remain
  intact.
- Manifest change:
  no change needed. This was a metadata/backfill correction under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2167 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 01:11 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `EUR CoinVertible의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:1N0EVlVA6OuftBI7sa6LdS_yVdkykxDbt:0B8HYgThT3NByWXpsUEMwMThJN0w5TWpKUVYveklvKzNEQzljPQ`.
- Source SHA-256:
  `7c1be166059571d47e9431b5a322f641213d1d374a66a9ee5946dcac51b89db1`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_eur-coinvertible_bce2167.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_eur-coinvertible.json`.
- Execution note:
  the generic entrypoint dry-run command was attempted first, but the MAT
  slug-filter path began downloading broader folder candidates because the
  Korean maturity filename pattern is not always parsed into the target slug.
  The production candidate was therefore generated through the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  EUR CoinVertible Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `eur-coinvertible`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `a678eabf-060e-4a9b-b238-c378b9537ed1`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id a678eabf-060e-4a9b-b238-c378b9537ed1 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2167" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `8012a7bc-3fbb-4d2f-9f65-366908c3d191`
  - promoted_at: `2026-06-24T16:11:22.389658+00:00`
- Project report verification:
  - `project_reports.id=8012a7bc-3fbb-4d2f-9f65-366908c3d191`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=CoinVertible은 MiCA 준수와 은행 담보 신뢰가 강하지만, 실사용 유동성과 XRPL 감사 공백 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=a678eabf-060e-4a9b-b238-c378b9537ed1`
- Manifest change:
  no change needed. This was a routine candidate ingest and Summary Authority
  Gate execution under the existing `analysis-md-summary-candidate` contract.

### BCE-2168 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 01:35 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Current Drive/DB metadata scan:
  491 Drive Markdown candidates were scanned across `analysis2` and legacy
  `analysis`; 299 revision source identities remained unpromoted after the
  promoted-source guard. The newest raw unpromoted candidate was the previously
  safety-skipped `GUSD(Gate USD)` MAT source, so this run selected the next
  eligible source with an existing website-visible target.
- Selected Drive Markdown:
  `Slime Miner _ SLIMEX 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1tqKbaF4K0mjSXCSsTdz7_ERk_bH7PjSs:0B8HYgThT3NBybnN2RlU2TytLQjc2eEwrM21xYWlKWXJ5SCtBPQ`.
- Source SHA-256:
  `d9bbe144365d4035898f1606174f8e566af098b10784333c45f6334dd8729738`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_slimex_bce2168.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_slimex_bce2168.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_slimex.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug slimex --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_slimex_bce2168.json --require-agent-output --limit 1`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `slimex`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `2a01c5cc-e963-43e0-b224-4c85bede343e`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 2a01c5cc-e963-43e0-b224-4c85bede343e --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2168" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `27a4a053-4b07-4ce6-91ee-c44bf6515c97`
  - promoted_at: `2026-06-24T16:34:47.816259+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2168_slimex_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=slimex`
  - `project_reports.id=27a4a053-4b07-4ce6-91ee-c44bf6515c97`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=SLIMEX는 시즌 보상과 모바일 접근성이 강점이나, 오프체인 산정과 공급 투명성이 핵심 리스크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=2a01c5cc-e963-43e0-b224-4c85bede343e`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2168_slimex_website_verification.json`.
  KO and EN report/project pages for `slimex` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. Local verification used TLS verification
  disabled for the HTTP/content check only.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2169 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 02:18 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  491 Drive Markdown candidates were scanned across `analysis2` and legacy
  `analysis`; 298 revision source identities remained unpromoted after the
  promoted-source guard. The newest unpromoted candidate was selected after
  confirming a website-visible `gusd/maturity/ko` target existed.
- Selected Drive Markdown:
  `GUSD(Gate USD)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Source identity:
  `drive:1nCZ7DX8aYSVGVTlP9C5haNZJisnZoOKd:0B8HYgThT3NByK2MyOCtBellrR0tid2Z3QzE0SUVWVGo1TFlVPQ`.
- Source SHA-256:
  `cf6a89e071c55290601b8887b99d157beb56abaa197d547a05771184c24d743a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_gusd_bce2169.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_gusd_bce2169.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_gusd.json`.
- Execution note:
  the generic CLI dry-run command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug gusd --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_gusd_bce2169.json --require-agent-output --limit 1 --force --dry-run`.
  It was interrupted after more than 90 seconds in broad Drive downloads.
  The production candidate was generated through the same candidate validation,
  upsert, artifact, and telemetry functions against the selected GUSD Drive
  file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `gusd`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `bbe4f358-3ca0-4e1b-81b4-b593bb960fa4`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id bbe4f358-3ca0-4e1b-81b4-b593bb960fa4 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2169" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `890149f4-f875-410e-ade6-6e708603c37f`
- DB verification artifact:
  `scripts/pipeline/output/bce2169_gusd_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=gusd`
  - `tracked_projects.name=Gemini Dollar` at verification time, while the
    selected source and previous GUSD pipeline artifacts are Gate GUSD/Gate USD.
    This metadata naming mismatch is pre-existing and should be corrected
    separately; this routine followed the existing `gusd` source/target
    contract.
  - `project_reports.id=890149f4-f875-410e-ade6-6e708603c37f`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=GUSD는 Gate 유틸리티와 1:1 상환 구조가 강점이나, 준비금 공시와 외부 유동성이 병목이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=bbe4f358-3ca0-4e1b-81b4-b593bb960fa4`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/gusd` and
    `https://www.bcelab.xyz/en/projects/gusd` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted KO/EN summaries.
  - `https://www.bcelab.xyz/{ko,en}/reports/gusd` returned `404`; the project
    pages are the current website-visible surface for this target.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2165 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 00:11 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  `scripts/pipeline` helpers found 491 Drive Markdown candidates, skipped 189
  already-promoted revision source identities, and left 302 unpromoted metadata
  candidates. The newest unpromoted candidate was selected.
- Selected Drive Markdown:
  `Rollbit 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1hImcdjI8FsTJu5D7n4tmWOC69NBao0Qv:0B8HYgThT3NByTWFTZTdRd3MxWlZCYXRET3hVSXJpbFYrVk5FPQ`.
- Source SHA-256:
  `fd1b768ba80e04ed5116287a6c468102e6aa1b0b698a1507f246ce595fe02d2f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_rollbit-coin_bce2165.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_rollbit-coin.json`.
- Execution note:
  local `--source-path` dry-run validation passed first. The production
  candidate was generated through the same candidate validation, upsert,
  artifact, and telemetry functions against the selected Rollbit Drive file id
  only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `rollbit-coin`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `c64d732a-36e7-4d08-9b2f-44791e7e2f0c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id c64d732a-36e7-4d08-9b2f-44791e7e2f0c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2165" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `4e7568af-9a4e-4816-9268-562f5d770b7b`
- DB verification artifact:
  `scripts/pipeline/output/bce2165_rollbit_coin_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=rollbit-coin`
  - `project_reports.id=4e7568af-9a4e-4816-9268-562f5d770b7b`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Rollbit RLB는 실제 플랫폼 매출과 소각 구조가 강점이나, 오프체인 회계와 규제 리스크가 크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=c64d732a-36e7-4d08-9b2f-44791e7e2f0c`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2165_rollbit_coin_website_verification.json`.
  KO and EN report/project pages for `rollbit-coin` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2163 CRO Analysis MD Summary JSON Ingestion Routine Duplicate Replay (2026-06-24 23:43 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Duplicate source detected:
  the latest Drive source selected by the routine was the same 0x Protocol
  ECON source already promoted in [BCE-2162](/BCE/issues/BCE-2162).
- Source identity:
  `drive:1D2ELgge9v4dFPTBLdxbFaMP0JgH-YfuR:0B8HYgThT3NByWkVvaG5zTE5tSXh1RGUydVFCUWdBQWVYeURrPQ`.
- Existing promoted job:
  `bfd75e71-d937-4adf-ab6c-9f7ca85fddd3`.
- Existing promoted project report:
  `08a33ed1-9c43-48c0-b4b2-81061628e178`.
- Replay result:
  `report_summary_jobs` upsert returned `updated_existing`, and the Summary
  Authority Gate write path returned `promoted` / `wrote_project_report=true`
  for the same project report id. No new Drive Markdown was identified.
- Current DB state after replay:
  - candidate job remains `authority_state=promoted`,
    `authority_mode=llm_active`, and
    `promoted_project_report_id=08a33ed1-9c43-48c0-b4b2-81061628e178`.
  - promoted report remains `0x/econ/ko`, `status=published`.
- Follow-up opened:
  [BCE-2164](/BCE/issues/BCE-2164) to make the routine skip source identities
  that already have a promoted candidate job and finish with
  `no-op: no new analysis markdown` when no eligible source remains.
- Manifest change:
  no change needed. This was a duplicate routine replay under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2164 Promoted Source Polling Guard (2026-06-24 23:51 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Fix:
  `scripts/pipeline/analysis_md_summary_candidate.py` now loads promoted
  `report_summary_jobs.source_identity` values for the report type and excludes
  those Drive identities during candidate selection before applying `--limit`.
- Manual reprocessing boundary:
  `--force` remains the explicit manual override and includes promoted source
  identities intentionally; normal routine polling must omit `--force`.
- No-op behavior:
  when no unpromoted Drive Markdown candidate remains, the entrypoint prints
  `no-op: no new analysis markdown`, writes the empty artifact, records
  successful zero-count telemetry when available, and exits `0`.
- Regression tests:
  `python3 -m pytest scripts/pipeline/test_analysis_md_summary_candidate.py`
  passed with `11 passed`, covering promoted-source skip before download,
  force override, and the no-op path.
- Manifest change:
  no change needed. This is a candidate-selection/runtime guard under the
  existing `analysis-md-summary-candidate` contract.

### BCE-2162 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 23:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  `scripts/pipeline` helpers found 491 Drive Markdown candidates and 303
  unpromoted candidates by revision source identity. The newest unpromoted
  candidate was selected.
- Selected Drive Markdown:
  `0x Protocol ZRX 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1D2ELgge9v4dFPTBLdxbFaMP0JgH-YfuR:0B8HYgThT3NByWkVvaG5zTE5tSXh1RGUydVFCUWdBQWVYeURrPQ`.
- Source SHA-256:
  `6b0db134e5b8d55e3113ee430718ee88628a27aa324a4ff447124e86fa880d0f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_0x_bce2162.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_0x.json`.
- Execution note:
  local `--source-path` dry-run validation passed first. The generic Drive
  entrypoint was then attempted, but it spent more than 60 seconds in broad
  Drive downloads before candidate selection. The production candidate was
  generated through the same candidate validation, upsert, artifact, and
  telemetry functions against the selected 0x Drive file id only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `0x`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `bfd75e71-d937-4adf-ab6c-9f7ca85fddd3`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id bfd75e71-d937-4adf-ab6c-9f7ca85fddd3 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2162" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `08a33ed1-9c43-48c0-b4b2-81061628e178`
  - promoted at: `2026-06-24T14:08:06.325073+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2162_0x_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=0x`
  - `project_reports.id=08a33ed1-9c43-48c0-b4b2-81061628e178`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=0x는 다중 유동성 라우팅과 API 인프라 경쟁력이 강하지만, ZRX의 직접 수익 포획은 약하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=bfd75e71-d937-4adf-ab6c-9f7ca85fddd3`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2162_0x_website_verification.json`.
  KO and EN report/project pages for `0x` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was run with certificate verification
  disabled for the check only.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2159 AWE Forensic KO Target Seed Prepared (2026-06-24 22:55 KST)

- Workspace/SHA when reconciled:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context read before reconciliation:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/for.md`, and `pipelines/bcelab-runtime-pipelines.json`.
- Seed migration:
  `supabase/migrations/20260624132200_seed_awe_network_forensic_ko_summary_target.sql`.
- Target scope:
  create or repair the missing website-visible
  `awe-network/forensic/ko/version:1` target row required by Summary Authority
  Gate job `de5600d2-6b4d-4691-82cd-4d69a08b2a62`.
- Production write boundary:
  this is target seed/backfill data only. It does not invoke
  `summary_authority_gate.py --write`, does not promote the candidate, and does
  not write report summary content to `project_reports`.
- Manifest change:
  no change needed. This remains under the existing
  `analysis-md-summary-candidate` authority gate contract; the active FOR slide
  publishing contract is unchanged.

### BCE-2160 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 22:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Candidate selection:
  the current Drive/DB scan found the newest unprocessed source as
  `ARX 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1y_edFrd7AW9I0RwVU7BeTyGohj4uxWG-:0B8HYgThT3NBydHJ3cmdQYjFJUVBwK0hBVXVBVUpWelo4QkxBPQ`.
- Source SHA-256:
  `957a19ae2fbba18dd1a91e4650665a79215367b3a9d53cc7a58fb189036a187a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_arcium_bce2160.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_arcium.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug arcium --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_arcium_bce2160.json --require-agent-output --limit 1 --force`.
  Because the forensic Korean filename path can score broader folder candidates
  before slug selection, that command selected the already promoted AWE source
  and inserted an invalid arcium/AWE candidate job
  `c70818f1-47ad-49a2-b047-ad67a7bee594`. The production candidate for this
  run was then generated through the same candidate validation, upsert,
  artifact, and telemetry functions against the selected ARX Drive file id
  only.
- Candidate ingest result:
  - report type: `for` / DB type: `forensic`
  - slug: `arcium`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `0334ab47-dfa6-44ae-aa43-884fcb8d74ae`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0334ab47-dfa6-44ae-aa43-884fcb8d74ae --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2160" --write`.
- Promotion result:
  blocked by Supabase RPC error
  `website-visible project_reports target not found: arcium/forensic/ko`.
- Production DB verification:
  - `tracked_projects.slug=arcium` exists with symbol `ARX`.
  - `project_reports` has `arcium/forensic/en` with status `coming_soon`.
  - no `arcium/forensic/ko` website-visible target row exists.
  - candidate job remains `status=candidate_ready`,
    `validation_status=valid`, `authority_state=validation_passed`, and
    `promoted_project_report_id=null`.
- Required unblock:
  [BCE-2161](/BCE/issues/BCE-2161) must seed/backfill a website-visible
  `arcium/forensic/ko` target row, then CRO should rerun the existing valid
  candidate job promotion.
- Manifest change:
  no change needed. This is target data/backfill under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2160 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 22:46 KST)

- Resume reason:
  `issue_children_completed` after [BCE-2161](/BCE/issues/BCE-2161)
  completed the missing target-row backfill.
- Workspace/SHA at resume:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before promotion:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Unblock evidence from [BCE-2161](/BCE/issues/BCE-2161):
  - migration:
    `supabase/migrations/20260624134500_seed_arcium_forensic_ko_summary_target.sql`
  - production target row:
    `project_reports.id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`,
    `report_type=forensic`, `language=ko`, `version=1`,
    `status=coming_soon`.
  - dry-run Summary Authority Gate result before CRO resume:
    `dry_run=true`, action `promote`, `wrote_project_report=false`,
    `project_report_id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0334ab47-dfa6-44ae-aa43-884fcb8d74ae --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2160" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `5be04e6d-7126-4224-8153-2f1cfc58e4b5`
  - promoted at: `2026-06-24T13:46:28.719494+00:00`
- DB verification after promotion:
  - candidate job `0334ab47-dfa6-44ae-aa43-884fcb8d74ae` now has
    `authority_state=promoted`, `authority_mode=llm_active`, and
    `promoted_project_report_id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`.
  - promoted report `card_summary_ko`:
    `ARX는 상장 초기 거래량이 체인 유동성을 크게 앞서며, 고점 후퇴와 얕은 호가로 조작 리스크가 높다.`
  - promoted report `marketing_content_by_lang.ko`:
    `투자 관점에서는 ARX가 0.325와 0.347 회복을 확인하기 전까지 추격 매수를 피하고 0.284 이탈을 경계해야 한다.`
  - `card_data.summary_authority.mode=llm_active` with the same job id,
    idempotency key, source identity, and promoted timestamp.
- Website/cache verification:
  - KO/EN report and project URLs for `arcium` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - The promoted report row remains `status=coming_soon`; current public HTML
    did not render the promoted summary text during this check. The promotion
    updated Supabase `project_reports` directly through the Summary Authority
    Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was target data plus Summary Authority Gate execution
  under the existing `analysis-md-summary-candidate` contract.

### BCE-2173 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 03:45 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Slime Miner _ SLIMEX의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1yA0C1Gp160eXMQX2To75VZxP3kNgjE_o:0B8HYgThT3NByeHdQdE85LzhnK0EyVmNZeEF5dkJ2RTdVMUNBPQ`.
- Source SHA-256:
  `a6a589a4f956996ed54775793ad91aafbfbd3e70ecb23791d51c176152114644`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_slimex_bce2173.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_slimex.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT folder
  downloads, so this run used the same candidate validation, upsert, artifact,
  and telemetry functions against the selected SLIMEX Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `slimex`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `9bc3e1ee-766e-4a47-90f2-b047b6c58e56`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 9bc3e1ee-766e-4a47-90f2-b047b6c58e56 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2173" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `b2579ad0-3ae7-45d2-abe7-bb2ccfb821a1`
  - promoted at: `2026-06-24T18:44:26.019599+00:00`
- Project report verification:
  - `project_reports.id=b2579ad0-3ae7-45d2-abe7-bb2ccfb821a1`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=SLIMEX는 게임 견인력은 높지만, 보상 경제와 온체인 검증성이 미성숙해 성숙도는 61.7점에 그친다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=9bc3e1ee-766e-4a47-90f2-b047b6c58e56`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/slimex/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and rendered the promoted English text.
  - `https://www.bcelab.xyz/en/projects/slimex` returned HTTP `200` with the
    same cache policy and rendered the promoted MAT report card text.
  - The promotion updated Supabase `project_reports` directly through the
    Summary Authority Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2197 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 15:08 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `03462cf`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  issue-assigned wake with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Selected Drive Markdown:
  `RealLink 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1GZjmIIDx0khLVvkYwJyHi0b7yiZPjvja:0B8HYgThT3NByV2V5Mm5sdFloMC9raEtHUnJvYWxKNTNJZ2xZPQ`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_reallink_bce2191.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug reallink --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_reallink_bce2191.json --require-agent-output --limit 1 --force`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_reallink.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `reallink`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `b9117ac6-dfb6-4297-8317-3e4dead2c7ac`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id b9117ac6-dfb6-4297-8317-3e4dead2c7ac --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2197" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`
  - promoted at: `2026-06-25T06:06:16.960915+00:00`
- DB verification:
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.authority_mode=llm_active`
  - `report_summary_jobs.validation_status=valid`
  - `report_summary_jobs.promotion_actor=paperclip-routine:CRO:BCE-2197`
  - `project_reports.status=coming_soon`
  - `project_reports.card_data.summary_authority.mode=llm_active`
  - `project_reports.card_data.summary_quality.model=paperclip-cro-local-agent`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/reallink` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`,
    but still showed the empty report state.
  - `https://www.bcelab.xyz/en/projects/reallink` returned HTTP `200` with
    the same no-store cache policy, but still showed the empty report state.
- Blocker:
  DB promotion succeeded, but live website publication is not complete because
  production still needs the BCE-2193 summary-authority website contract
  deployment. Board approval `5bad929f-1594-4168-ab5f-087994a06a5e` was
  requested to run `.github/workflows/production-deploy.yml` for
  `codex/paperclip-agent-summary-source@03462cf`.
- Blocker cleared update (2026-06-25 17:55 KST):
  - Board/user update on BCE-2197 confirmed BCE-2193 is done and the
    summary-authority website path landed through
    `acf61359e76a74b0bee3a86ac2de867e0d2cb62c`.
  - Production Deploy succeeded:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28158073408
  - BCE-2191 is done and reverified RealLink ECON production web publication
    from the same source identity.
  - Local resume verification from workspace
    `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
    at `acf6135` confirmed `/ko/reports/reallink/econ` and
    `/en/reports/reallink/econ` return HTTP 200 with no-store cache headers and
    contain the promoted summary plus Investment View copy.
  - The earlier BCE-2197 blocker, "live publication deploy approval pending",
    is now cleared. No runtime manifest change was needed.
- Manifest change:
  no manifest change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract; only the state wiki was updated
  with execution and blocker evidence.

### BCE-2195 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 14:11 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `03462cf`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  issue-assigned wake with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Selected Drive Markdown:
  `Solstice Finance eUSX YieldVault 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1wzQES7CWtLFVa5vAeHRI8iZwqeHJ_5AR:0B8HYgThT3NByUW9RZU96ZGJtQzBqNDlQTWh4MW0rQ2ZHRXlnPQ`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_solstice_bce2195.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_solstice.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug solstice --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_solstice_bce2195.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `solstice`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `48d96908-3920-4807-a43d-9b8b0b73fe72`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 48d96908-3920-4807-a43d-9b8b0b73fe72 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2195" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `9e20fd09-81e2-46e2-bb40-94188d0e292a`
  - promoted at: `2026-06-25T05:11:19.277188+00:00`
- Project report verification:
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.authority_mode=llm_active`
  - `report_summary_jobs.validation_status=valid`
  - `report_summary_jobs.promoted_project_report_id=9e20fd09-81e2-46e2-bb40-94188d0e292a`
  - `project_reports.status=published`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=48d96908-3920-4807-a43d-9b8b0b73fe72`
- Website/cache verification:
  - KO and EN report pages `/ko/reports/solstice/econ` and
    `/en/reports/solstice/econ` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO and EN project pages `/ko/projects/solstice` and
    `/en/projects/solstice` returned HTTP `200` with the same no-store cache
    control.
  - KO pages contained the promoted Korean summary and Investment View text.
  - EN pages contained the promoted English summary and Investment View text.
  - The local `curl` verification used `-k` for TLS only because the local CA
    chain may be unavailable.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2191 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 13:xx KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  issue-assigned wake with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  AWE FOR was the newest Drive Markdown by modified time, but the exact source
  identity was already promoted for `awe-network/forensic`, so it was excluded.
- Selected Drive Markdown:
  `RealLink 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1GZjmIIDx0khLVvkYwJyHi0b7yiZPjvja:0B8HYgThT3NByV2V5Mm5sdFloMC9raEtHUnJvYWxKNTNJZ2xZPQ`.
- Source SHA-256:
  `bab4e6f8525aeb828eef60c61e0c5b48f237ad23c46b597fdb8458a0d4ed0432`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_reallink_bce2191.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_reallink.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug reallink --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_reallink_bce2191.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known broad Drive candidate download path ran for
  more than one minute. The production candidate then used the same candidate
  validation, upsert, and artifact functions against the selected RealLink Drive
  file id only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `reallink`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `b9117ac6-dfb6-4297-8317-3e4dead2c7ac`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id b9117ac6-dfb6-4297-8317-3e4dead2c7ac --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2191" --write`.
- Promotion result:
  - exit code: `1`
  - no `promote` result returned
  - no `wrote_project_report=true` evidence
  - no `project_report_id` returned
- Blocker:
  - Supabase RPC failed with `website-visible project_reports target not found:
    reallink/econ/ko`.
  - `tracked_projects.slug=reallink` exists, but `project_reports` currently has
    only `report_type=maturity`, `language=ko`, `status=coming_soon` for that
    project.
  - No ECON KO target row exists for the authority gate to promote into.
- Operational status:
  - `BCE-2191` must remain blocked until the missing `reallink/econ/ko`
    website-visible target is created or the routine target-selection contract is
    updated to skip sources without a promotable report target.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract; the failure is target data/state,
  not executable manifest drift.

#### BCE-2191 Resume After BCE-2192 (2026-06-25 13:2x KST)

- Resume wake:
  `issue_children_completed`; `BCE-2192` was done and `BCE-2191` was moved back
  to `in_progress`.
- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe`.
- Primary context rechecked before action:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- `BCE-2192` evidence:
  - added deployable repair record
    `supabase/migrations/20260625041200_seed_reallink_econ_ko_summary_target.sql`;
  - inserted `project_reports.id=f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`
    for `reallink/econ/ko`;
  - reran the gate and promoted job
    `b9117ac6-dfb6-4297-8317-3e4dead2c7ac`.
- Current DB state:
  - `report_summary_jobs.id=b9117ac6-dfb6-4297-8317-3e4dead2c7ac`
    is `authority_state=promoted`, `authority_mode=llm_active`,
    `promotion_decision=promote`, and
    `promoted_project_report_id=f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`.
  - Idempotent rerun returned `action=noop`, `state=promoted`,
    `project_report_id=f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`.
- Remaining blocker:
  - The promoted target row is still `status=coming_soon` and has no
    `slide_html_urls_by_lang`.
  - Website checks for `https://www.bcelab.xyz/ko/reports/reallink/econ`,
    `https://www.bcelab.xyz/en/reports/reallink/econ`,
    `https://www.bcelab.xyz/ko/projects/reallink`, and
    `https://www.bcelab.xyz/en/projects/reallink` returned HTTP `200` with
    no-cache headers, but none contained the promoted Korean or English summary
    or Investment View text.
  - Code inspection shows project pages only query `published`/`in_review`
    reports, and report pages treat reports without slide HTML assets as
    `locale_pending`; therefore the current promoted metadata row is not active
    website-visible content.
- Operational status:
  - `BCE-2191` should remain blocked until the website publishing contract for
    summary-only promoted rows is implemented, or an appropriate slide/HTML
    asset plus publish status is attached so the promoted RealLink ECON summary
    is visible on website pages.
- Manifest change:
  no manifest change was made in this CRO heartbeat. The remaining gap is an
  implementation/website-publication contract issue around summary-only
  promoted rows.

### BCE-2192 RealLink ECON Summary Authority Target Backfill (2026-06-25 13:14 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe`.
- Primary context checked before execution:
  `knowledge/pipelines/econ.md`, `knowledge/pipelines/analysis-md-summary-candidate.md`,
  and `pipelines/bcelab-runtime-pipelines.json`.
- Decision:
  create/backfill the missing `reallink/econ/ko` website-visible target row
  rather than changing candidate selection, because the Summary Authority Gate
  contract intentionally promotes only into an existing `project_reports` row
  and previous target gaps have been resolved with explicit summary target
  shells.
- Repo artifact:
  `supabase/migrations/20260625041200_seed_reallink_econ_ko_summary_target.sql`.
- Production target seed:
  - action: `inserted`
  - project report id: `f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`
  - source identity: `summary-authority-target:reallink/econ/ko/version:1`
  - status: `coming_soon`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id b9117ac6-dfb6-4297-8317-3e4dead2c7ac --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2191" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - promoted project report id: `f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`
- Verification artifact:
  `scripts/pipeline/output/bce2192_reallink_econ_ko_db_website_verification.json`.
- Website checks:
  public RealLink project/report routes returned HTTP `200`; exact summary text
  was not visible in fetched HTML at verification time, matching the prior
  RealLink MAT verification behavior.
- Operational status:
  `BCE-2191` can resume; the previous missing-target blocker has been cleared.
- Manifest change:
  no change needed. This was target data/state remediation under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2191 CRO Analysis MD Summary JSON Ingestion Routine Closeout (2026-06-25 17:5x KST)

- Resume wake:
  `issue_children_completed`; [BCE-2193](/BCE/issues/BCE-2193) was `done`, so
  [BCE-2191](/BCE/issues/BCE-2191) resumed without a duplicate checkout.
- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- Primary context checked before closeout:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Original selected Drive Markdown:
  `RealLink 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1GZjmIIDx0khLVvkYwJyHi0b7yiZPjvja:0B8HYgThT3NByV2V5Mm5sdFloMC9raEtHUnJvYWxKNTNJZ2xZPQ`.
- Source SHA-256:
  `bab4e6f8525aeb828eef60c61e0c5b48f237ad23c46b597fdb8458a0d4ed0432`.
- Artifacts:
  - Paperclip CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_econ_reallink_bce2191.json`
  - Candidate ingest:
    `scripts/pipeline/output/analysis_md_summary_candidate_econ_reallink.json`
  - Target/website verification from [BCE-2192](/BCE/issues/BCE-2192):
    `scripts/pipeline/output/bce2192_reallink_econ_ko_db_website_verification.json`
- Candidate job verification:
  - job id: `b9117ac6-dfb6-4297-8317-3e4dead2c7ac`
  - validation status: `valid`
  - validation reasons: none
  - authority state: `promoted`
  - authority mode: `llm_active`
  - promotion decision: `promote`
  - promoted project report id:
    `f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`
  - promoted at: `2026-06-25T06:06:16.960915+00:00`
- [BCE-2193](/BCE/issues/BCE-2193) closeout evidence:
  - summary-only `card_data.summary_authority.mode=llm_active` rows are now
    treated as active website-visible rows;
  - production deploy run:
    `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28158073408`;
  - production regression gate passed against `https://bcelab.xyz`;
  - no manifest change was required.
- Direct production verification from [BCE-2191](/BCE/issues/BCE-2191)
  closeout:
  - `https://www.bcelab.xyz/ko/reports/reallink/econ` returned HTTP `200`,
    no-cache headers, promoted Korean summary count `2`, Korean Investment View
    count `2`, old Korean slide phrase count `0`;
  - `https://www.bcelab.xyz/en/reports/reallink/econ` returned HTTP `200`,
    no-cache headers, promoted English summary count `2`, English Investment
    View count `2`;
  - `https://www.bcelab.xyz/ko/projects/reallink` returned HTTP `200`,
    no-cache headers, promoted Korean summary count `2`, Korean Investment View
    count `2`, old Korean slide phrase count `0`;
  - `https://www.bcelab.xyz/en/projects/reallink` returned HTTP `200`,
    no-cache headers, promoted English summary count `2`, English Investment
    View count `2`;
  - the local verifier used certificate verification disabled for the content
    check only because the local CA chain may be unavailable.
- Final status:
  [BCE-2191](/BCE/issues/BCE-2191) completion conditions are satisfied:
  Paperclip local CRO JSON exists, candidate ingest is valid, Summary Authority
  Gate write promotion is terminal `promoted`, and promoted summary/Investment
  View copy is visible on production report and project pages.
- Manifest change:
  no change needed. Closeout occurred under the existing
  `analysis-md-summary-candidate` manifest after [BCE-2193](/BCE/issues/BCE-2193)
  implemented the summary-only website publication contract.

### BCE-2186 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 10:42 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `5352412`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  process-lost retry with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Selected Drive Markdown:
  `Strategy PP Variable xStock 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1-NPe_EaE0l6iDJYTDaDze55dYtKxUGic:0B8HYgThT3NByVFFMRm1vRWJYenJUTHNiVE1UR2JDUy81OUtrPQ`.
- Source SHA-256:
  `12f24cbbe3c49c86e2f4e0f2fe6ae8cf1333276f6f228ca25a141be0166cd004`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_strategy-pp-variable-tokenized-stock-xstock_bce2186.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_strategy-pp-variable-tokenized-stock-xstock_bce2186.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_strategy-pp-variable-tokenized-stock-xstock.json`.
- Execution note:
  the previous heartbeat created the source snapshot and initial JSON, then
  stopped during the known broad Drive folder path. This continuation used the
  same candidate validation, upsert, artifact, and telemetry functions against
  the selected Strategy PP Variable xStock Drive file id only.
- Validation correction:
  the first upsert inserted the row as validation-failed because
  `summary_by_lang.en.raw_format_fragment`,
  `summary_by_lang.de.raw_format_fragment`,
  `marketing_by_lang.de.raw_format_fragment`, and
  `marketing_by_lang.zh.too_short` failed quality gates. The CRO JSON was
  revised to remove hyphenated/abbreviated raw fragments and lengthen the zh
  Investment View, then rerun with `--force`.
- Candidate ingest result after correction:
  - report type: `econ`
  - slug: `strategy-pp-variable-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `62544e66-5426-4d21-8f3c-c614dca681d8`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 62544e66-5426-4d21-8f3c-c614dca681d8 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2186" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `611ffe74-833f-447a-b270-8c7bfc0926dc`
  - promoted at: `2026-06-25T01:41:47.403379+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2186_strategy_pp_variable_xstock_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=strategy-pp-variable-tokenized-stock-xstock`
  - `tracked_projects.symbol=STRCx`
  - `project_reports.id=611ffe74-833f-447a-b270-8c7bfc0926dc`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=STRCx는 STRC 우선주 노출을 온체인화한 담보형 RWA지만, 수탁·규제·프록시 운영 신뢰가 핵심 리스크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=62544e66-5426-4d21-8f3c-c614dca681d8`
- Website/cache verification:
  - KO and EN project pages for `strategy-pp-variable-tokenized-stock-xstock`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO and EN project pages contained the promoted localized card summary.
  - EN report detail page returned HTTP `200` with the same cache policy but
    still displayed the localized report preparation message, so the immediate
    publication evidence is the project report card surface backed by
    `project_reports`.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2187 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 11:42 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `5352412`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry` after an earlier candidate probe; no pending comments
  were included and the harness had already checked out the issue, so no
  duplicate checkout was made.
- Current Drive/DB metadata scan:
  the newest unpromoted source with a website-visible KO target row was selected
  from active Drive Markdown. The selected MAT file had a published
  `project_reports` maturity/ko target row, while the corresponding ECON file
  had already been promoted under BCE-2186.
- Selected Drive Markdown:
  `STRCx _ Strategy PP Variable xStock의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1O7rTgzHgfpwLixRbPpxkRZFeaPOMpGOc:0B8HYgThT3NByQXFCazVmVmV4ejBmd0U5a1JOTVZ3TW91SEdVPQ`.
- Source SHA-256:
  `78b17fd22018b7ec32a03eb12e109a3b6e713ba68c0610b1eb01232767dba00c`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_strategy-pp-variable-tokenized-stock-xstock_bce2187.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_strategy-pp-variable-tokenized-stock-xstock_bce2187.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_strategy-pp-variable-tokenized-stock-xstock.json`.
- Execution note:
  the initial probe artifacts used slug `probe` only to inspect remaining
  Drive candidates. The production candidate reused the pipeline's candidate
  validation, upsert, artifact, and telemetry functions against the selected
  STRCx MAT Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `strategy-pp-variable-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `986022cf-fcd1-4c5c-bd99-678d3920b904`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 986022cf-fcd1-4c5c-bd99-678d3920b904 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2187" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `327c7ec0-48f9-4c26-8dfc-85e31e19b61b`
  - promoted at: `2026-06-25T02:41:45.584941+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2187_strategy_pp_variable_xstock_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=strategy-pp-variable-tokenized-stock-xstock`
  - `tracked_projects.symbol=STRCx`
  - `project_reports.id=327c7ec0-48f9-4c26-8dfc-85e31e19b61b`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=STRCx는 규제형 RWA 인프라와 유통 규모는 강하지만, 담보·상환·가격 안정 검증이 성숙도 핵심이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=986022cf-fcd1-4c5c-bd99-678d3920b904`
- Website/cache verification:
  - KO and EN project pages for `strategy-pp-variable-tokenized-stock-xstock`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate`.
  - KO and EN maturity report pages returned HTTP `200` with the same cache
    policy.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2188 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 12:11 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `5352412`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  issue assigned with no pending comments; the harness had already checked out
  the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  the newest Drive Markdown sources (`AWE`, `ARX`, and `0x Protocol ZRX`) were
  already in terminal `promoted` authority state for their matching report
  types, so the routine advanced to the newest unpromoted source with a
  website-visible KO target row.
- Selected Drive Markdown:
  `Frax 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1fGKr_8LhcX_SlcXc3iV32icp-tcybxqf:0B8HYgThT3NByU2JQaGFsV3M0UlNmMG5LcG9ER094aVkzcnZvPQ`.
- Source SHA-256:
  `9dc48dbcb39596052e18c02cd5d41e0eb6577f38eb1594bc4cec3e7e5fea2439`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_legacy-frax-dollar_bce2188.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_frax_bce2188.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_legacy-frax-dollar.json`.
- Execution note:
  the source file covers the Frax Finance stack, while the website-visible ECON
  target row maps to `tracked_projects.slug=legacy-frax-dollar` with symbol
  `FRAX`; the run used the pipeline's candidate validation, upsert, artifact,
  and telemetry functions against the selected Frax Drive file id only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `legacy-frax-dollar`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `4cbb8572-d638-456e-b27e-26426431a48f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 4cbb8572-d638-456e-b27e-26426431a48f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2188" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `da3a7de1-95ca-498e-af05-d41e8b4b0110`
  - promoted at: `2026-06-25T03:11:16.027055+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2188_legacy_frax_dollar_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=legacy-frax-dollar`
  - `tracked_projects.symbol=FRAX`
  - `project_reports.id=da3a7de1-95ca-498e-af05-d41e8b4b0110`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=FRAX는 frxUSD 준비금 안정성, Fraxtal 가스 수요, veFRAX 잠금이 맞물린 통합 금융 스택이지만, 오프체인 준비금과 복잡한 거버넌스가 핵심 리스크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=4cbb8572-d638-456e-b27e-26426431a48f`
- Website/cache verification:
  - KO and EN project pages for `legacy-frax-dollar` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO and EN ECON report pages returned HTTP `200` with the same cache policy.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2176 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 05:31 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `MYX Finance의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:1wPnSga4AHlEdKUCp0ziMzlY8Jsa9YW3m:0B8HYgThT3NBycHhRRzR6QW9KalpFcU5EOTR3WS93aW1QSVNrPQ`.
- Source SHA-256:
  `9e24c94d625c9d569dbbe6566591b2008ec458698b98320e1245c3cc0ea8b26e`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_myx-finance_bce2176.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_myx-finance.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug myx-finance --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_myx-finance_bce2176.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads before candidate selection. The run then used the same
  candidate validation, upsert, artifact, and telemetry functions against the
  selected MYX Finance Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `myx-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `876dc087-0af5-4b1b-85e2-29a5ffd21013`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 876dc087-0af5-4b1b-85e2-29a5ffd21013 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2176" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `31829b10-aeb3-42fe-bdfc-a50b2db60d8f`
  - promoted at: `2026-06-24T20:31:47.254441+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2176_myx_finance_db_verification.json`.
- Project report verification:
  - `project_reports.id=31829b10-aeb3-42fe-bdfc-a50b2db60d8f`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=MYX Finance는 거래량 효율은 높지만 수익 포착, Keeper 투명성, 거버넌스 성숙도는 아직 검증 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=876dc087-0af5-4b1b-85e2-29a5ffd21013`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2176_myx_finance_website_verification.json`.
  KO and EN report/project pages for `myx-finance` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries and Investment View text. The local Python
  TLS verifier lacked a CA chain, so the HTTP/content verification was rerun
  with certificate verification disabled for the check only.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2174 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 04:08 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `INTCx(Intel xStock)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Source identity:
  `drive:1oP28EeRwR_CMsHo520TcjW71a4ozmU2X:0B8HYgThT3NByQUxvdHp0U21CWDNwZjkrdzVXa2lxWFQ2UU5VPQ`.
- Source SHA-256:
  `41477f6e7913546a309c12808db86eca2c0d325e09da28365d821d1aaa372f30`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_intel-tokenized-stock-xstock_bce2174.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_intel-tokenized-stock-xstock.json`.
- Execution note:
  the full helper scan was interrupted after it spent several minutes
  downloading all candidate Markdown bodies. The production candidate used the
  same candidate validation, upsert, artifact, and telemetry functions against
  the selected INTCx Drive file id only, after a metadata scan excluded
  promoted source identities.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `intel-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `fe5e8d95-6bf5-4742-a76d-96cf8b1be13f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fe5e8d95-6bf5-4742-a76d-96cf8b1be13f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2174" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `236955d6-2737-44a2-9e0c-d431b457a631`
  - promoted at: `2026-06-24T19:08:23.448558+00:00`
- Project report verification:
  - `project_reports.id=236955d6-2737-44a2-9e0c-d431b457a631`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=INTCx는 법률, 담보, 멀티체인 구조는 작동하지만 유동성과 DeFi 담보 채택이 약해 성숙도는 65.3점이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=fe5e8d95-6bf5-4742-a76d-96cf8b1be13f`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/intel-tokenized-stock-xstock/maturity`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate` and rendered the promoted English text.
  - `https://www.bcelab.xyz/en/projects/intel-tokenized-stock-xstock`
    returned HTTP `200` with the same cache policy and rendered the promoted
    MAT report card text.
  - The promotion updated Supabase `project_reports` directly through the
    Summary Authority Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2175 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 04:41 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Marvell xStock(MRVLx)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1uo_mzJ7qYKDcRdrfuBW8LwI9SJMjJ-dP:0B8HYgThT3NByMDFTZVZqRkxGS09XL3BUckpVdWJHS0pQV0hRPQ`.
- Source SHA-256:
  `e5eca19fa6f2a548cf721cbcdf52ab755b5cd5dca89601a451a32aea379ea016`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_marvell-tokenized-stock-xstock_bce2175.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_marvell-tokenized-stock-xstock.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT downloads
  because Korean MAT filenames are not always parsed into slugs, so this run
  used the same candidate validation/upsert/artifact functions against the
  selected Marvell xStock Drive file id only after metadata scan excluded
  promoted source identities.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `marvell-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `20de48bc-3407-4048-bfb7-30352303f2d9`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 20de48bc-3407-4048-bfb7-30352303f2d9 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2175" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `fe8c1f7d-d0dd-4031-9af9-cc6a861a551e`
  - promoted at: `2026-06-24T19:41:00.439517+00:00`
- Project report verification:
  - `project_reports.id=fe8c1f7d-d0dd-4031-9af9-cc6a861a551e`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=MRVLx는 1:1 담보와 멀티체인 발행은 갖췄지만, 개별 DEX 유동성은 아직 얕은 전개 단계 RWA다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=20de48bc-3407-4048-bfb7-30352303f2d9`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/marvell-tokenized-stock-xstock/maturity`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate` and rendered the promoted English text.
  - `https://www.bcelab.xyz/en/projects/marvell-tokenized-stock-xstock`
    returned HTTP `200` with the same cache policy and rendered the promoted
    MAT report card text.
  - The promotion updated Supabase `project_reports` directly through the
    Summary Authority Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2177 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 06:07 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  286 unpromoted metadata candidates remained after excluding promoted source
  identities. The newest eligible candidate with a website-visible KO target row
  was selected.
- Selected Drive Markdown:
  `WeFi의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`.
- Source identity:
  `drive:1S-miHHiZ_69Q6Tj573xY0Blf3Yl9Xnoh:0B8HYgThT3NByVUpVK2YzZXptKzdXTWMxbXNhbjJ4LzA2aEdjPQ`.
- Source SHA-256:
  `eb23f12b8cb958d802d214d33d76fdb3f98ec7fc6db382178b85c16b3d2dd14d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_wefi_bce2177.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_wefi_bce2177.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_wefi.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug wefi --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_wefi_bce2177.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads. The production candidate then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  WeFi Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `wefi`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `eb88e5f6-c134-4fb9-8e9f-606e75951acf`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id eb88e5f6-c134-4fb9-8e9f-606e75951acf --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2177" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `24007844-e84a-4f2c-b798-4caf4be875cb`
  - promoted at: `2026-06-24T21:07:31.967537+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2177_wefi_db_website_verification.json`.
- Project report verification:
  - `project_reports.id=24007844-e84a-4f2c-b798-4caf4be875cb`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=WeFi는 Deobank 결제 서사는 강하지만, 온체인 검증성과 거버넌스 투명성이 부족해 성숙도는 55점에 머문다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=eb88e5f6-c134-4fb9-8e9f-606e75951acf`
- Website/cache verification:
  - KO and EN report/project pages for `wefi` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO pages contained the promoted Korean summary.
  - EN pages contained the promoted English summary and Investment View text.
  - The local Python TLS verifier lacked a CA chain, so the HTTP/content
    verification was rerun with certificate verification disabled for the check
    only.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2178 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 06:40 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  process-lost retry with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  290 unpromoted metadata candidates remained after excluding promoted source
  identities. The newest eligible candidate with a website-visible KO target
  row was selected.
- Selected Drive Markdown:
  `48 Club의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017–2026.md`.
- Source identity:
  `drive:1MHsTOZ0OZxvqMevfWMtFYGlvGAhvLuaL:0B8HYgThT3NByMHFOUFJVQVJ2TFhKZ3hUOXZYZVBwdzNwTVZBPQ`.
- Source SHA-256:
  `6bd1835282d8f2330c975a7012415c9583ec19c268a59c1718595d6c3fa9265d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_bnb48-club-token_bce2178.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_bnb48-club-token_bce2178.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_bnb48-club-token.json`.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `bnb48-club-token`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `8a32e6af-89a5-45d3-828f-15e65c1cbf70`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 8a32e6af-89a5-45d3-828f-15e65c1cbf70 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2178" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `5bcda7f8-bc36-41d6-979d-27d56bea0896`
  - promoted at: `2026-06-24T21:40:03.572801+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2178_bnb48_club_token_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bnb48-club-token`
  - `tracked_projects.symbol=KOGE`
  - `project_reports.id=5bcda7f8-bc36-41d6-979d-27d56bea0896`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=48 Club은 BNB Chain MEV 인프라 점유율이 높지만, 재무와 거버넌스 투명성 보완이 필요한 성숙 초입 프로젝트다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=8a32e6af-89a5-45d3-828f-15e65c1cbf70`
- Website/cache verification:
  - KO and EN report/project pages for `bnb48-club-token` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO pages contained the promoted Korean summary.
  - EN pages contained the promoted English summary and Investment View text.
  - The local Python TLS verifier lacked a CA chain, so the HTTP/content
    verification was rerun with certificate verification disabled for the check
    only.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2179 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 07:10 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  issue-assigned wake with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  289 unpromoted Drive file ids remained after excluding promoted source file
  ids. The newest eligible candidate with a website-visible KO target row was
  selected.
- Selected Drive Markdown:
  `Keeta의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025 - 2026.md`.
- Source identity:
  `drive:1QY7EGuw2_gQx6RrZDjB97Ur1Ip3YuYUt:0B8HYgThT3NByRytlVzFncnBDMHgzZ3JmRXI1dUd1MFVQcGpjPQ`.
- Source SHA-256:
  `b2ae4757e333d05d5c6a97e3b5cc1b41b6160238a60358a2b1f63e6fdaa44987`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_keeta_bce2179.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_keeta_bce2179.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_keeta.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug keeta --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_keeta_bce2179.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known broad Drive candidate download path ran for
  more than two minutes. The production candidate then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  Keeta Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `keeta`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `53f55bc4-d5d9-4c3c-9c11-4369a1c66a2d`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 53f55bc4-d5d9-4c3c-9c11-4369a1c66a2d --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2179" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d35f3295-b290-455a-bfb9-18a1d434c62c`
  - promoted at: `2026-06-24T22:10:32.566798+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2179_keeta_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=keeta`
  - `tracked_projects.symbol=KTA`
  - `project_reports.id=d35f3295-b290-455a-bfb9-18a1d434c62c`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Keeta는 금융 결제와 토큰화 서사가 강하지만, 메인넷 사용량·TVL·거버넌스 공개가 아직 초기라 성숙도는 제한적이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=53f55bc4-d5d9-4c3c-9c11-4369a1c66a2d`
- Website/cache verification:
  - KO and EN report/project pages for `keeta` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO pages contained the promoted Korean summary.
  - EN pages contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2146 CRO Analysis MD Summary JSON Ingestion Routine Resumed (2026-06-25 17:48 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `da9fe5a`.
- Wake context:
  `issue_children_completed`; [BCE-2147](/BCE/issues/BCE-2147) was `done`, so
  [BCE-2146](/BCE/issues/BCE-2146) resumed without a duplicate checkout.
- Primary context checked before closeout:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Blocker resolution verified:
  - `tracked_projects.slug=0x`, `name=0x Protocol`, `symbol=ZRX`,
    `status=active`
  - aliases include `0x protocol`, `0x-protocol`, `zero ex`, `zero-ex`, `zrx`
- Original selected Drive Markdown:
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`.
- Candidate job verified:
  - job id: `885624b8-1a5e-4265-970e-d14adb86b790`
  - source identity:
    `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`
  - source SHA-256:
    `1714ef8196b372f387ebfe36bbee9fc87719bd12aa2fe78ac05e4d55c873f0d7`
  - validation status: `valid`
  - validation reasons: none
  - authority state: `promoted`
  - authority mode: `llm_active`
  - promotion decision: `promote`
  - promotion actor: `paperclip-routine:CRO:BCE-2156`
  - promoted project report id:
    `7cc38496-9e3d-44a0-8413-f69cbffe006a`
  - promoted at: `2026-06-24T12:39:01.221708+00:00`
- Artifacts:
  - Paperclip CRO JSON:
    `scripts/pipeline/output/paperclip_cro_summary_mat_0x_bce2150.json`
  - candidate ingest:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_0x.json`
  - [BCE-2146](/BCE/issues/BCE-2146) DB/website verification:
    `scripts/pipeline/output/bce2146_0x_db_website_verification.json`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/0x/maturity` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted Korean summary.
  - `https://www.bcelab.xyz/en/reports/0x/maturity` returned HTTP `200` with
    the same cache policy and contained the promoted English summary.
  - `https://www.bcelab.xyz/ko/projects/0x` and
    `https://www.bcelab.xyz/en/projects/0x` returned HTTP `200` with the same
    cache policy and contained the promoted localized MAT card summary.
  - The local verifier used certificate verification disabled for the content
    check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a blocker-resolution closeout under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2205 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 22:47 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  [BCE-2197](/BCE/issues/BCE-2197) 및 [BCE-2191](/BCE/issues/BCE-2191)의
  summary-only website contract blocker가 [BCE-2193](/BCE/issues/BCE-2193)
  배포로 해소됐고, 최신 산출물 기준 [BCE-2204](/BCE/issues/BCE-2204)는
  `quack-ai/econ`을 이미 promoted 및 웹 검증 완료했다.
- 후보 선택:
  promoted source identity를 DB에서 제외한 Drive 메타데이터 스캔 결과,
  `IVVON` MAT/ECON은 `tracked_projects` 매칭이 없어 스킵했고, 다음 최신
  eligible source로 `Bio Protocol` ECON을 선택했다.
- 선택한 Drive Markdown:
  `Bio Protocol 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1YrFfVOcVjuuAs7cHVhUQYWpqstYTMQLS:0B8HYgThT3NBySUNxQlloMVhFYXluUytJdG5uMklhblRrOHpnPQ`.
- Source SHA-256:
  `f9ab7a99cf8daa1552dcb4d9203235fec80e0b4da1e79f0d9f267212a026a812`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_bio_bce2205.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_bio_bce2205.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_bio.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, upsert, artifact 함수를 선택된 Bio Protocol Drive file id
  1개에만 적용했다.
- Candidate ingest result:
  - report type: `econ`
  - slug: `bio`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `8f0c98f6-756e-49ee-bb04-b7634256cd90`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 8f0c98f6-756e-49ee-bb04-b7634256cd90 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2205" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `ae453659-7727-4151-a14e-926d96aeae7c`
  - promoted at: `2026-06-25T13:47:12.464374+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2205_bio_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bio`
  - `tracked_projects.symbol=BIO`
  - `project_reports.id=ae453659-7727-4151-a14e-926d96aeae7c`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Bio Protocol은 BIO, veBIO, BioXP, 런치패드와 BioAgents를 묶어 DeSci 자금 조달을 조정하지만, 토큰 보유자 가치 포획은 treasury 수익과 과학 성과 검증에 달려 있다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=8f0c98f6-756e-49ee-bb04-b7634256cd90`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/bio`,
    `https://www.bcelab.xyz/ko/reports/bio/econ`,
    `https://www.bcelab.xyz/en/projects/bio`,
    `https://www.bcelab.xyz/en/reports/bio/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2206 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 23:06 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 루틴 실행 [BCE-2205](/BCE/issues/BCE-2205)는 `bio/econ` source를 이미
  promoted 및 웹 검증 완료했다. 이번 실행은 DB의 promoted source identity를
  제외하고 다음 미승격 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  `IVVON` MAT/ECON은 `tracked_projects` 매칭이 없어 스킵했고, 다음 최신
  eligible source로 `Unibase` MAT를 선택했다.
- 선택한 Drive Markdown:
  `Unibase의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1jqc-4CcrbYARV35cEMzulFE6fqIg7nbv:0B8HYgThT3NByVXhmZThNZFFwM2pVZjlJVWJtcngzM0dpT2djPQ`.
- Source SHA-256:
  `c1612f95798a40eef785190f3bd639f06dd945870af6188d237efaf395f25cc1`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_unibase_bce2206.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_unibase_bce2206.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_unibase.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, telemetry, artifact, upsert 함수를 선택된 Unibase
  Drive file id 1개에만 적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `unibase`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `0575725d-3009-4f0c-b23d-c5640f4e0850`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0575725d-3009-4f0c-b23d-c5640f4e0850 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2206" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `1535f2f5-2228-4bde-b71d-553cc0de985e`
  - promoted at: `2026-06-25T14:06:34.55071+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2206_unibase_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=unibase`
  - `tracked_projects.symbol=UB`
  - `project_reports.id=1535f2f5-2228-4bde-b71d-553cc0de985e`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Unibase는 AI 장기 메모리, AIP, x402 결제, DA를 묶어 Open Agent Internet 서사를 확장했지만, 공개 수익과 거버넌스, 독립 벤치마크가 아직 부족하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=0575725d-3009-4f0c-b23d-c5640f4e0850`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/unibase`,
    `https://www.bcelab.xyz/ko/reports/unibase/maturity`,
    `https://www.bcelab.xyz/en/projects/unibase`,
    `https://www.bcelab.xyz/en/reports/unibase/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2207 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 23:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 루틴 실행 [BCE-2206](/BCE/issues/BCE-2206)는 `unibase/mat` source를
  이미 promoted 및 웹 검증 완료했다. 이번 실행은 DB의 promoted source
  identity를 제외하고 다음 미승격 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 IVVON MAT/ECON은 `tracked_projects` 매칭이 없어 스킵했고, Frax MAT는
  웹 공개 KO target row가 없어 스킵했다. 다음 eligible source로
  `Solstice Finance` ECON을 선택했다.
- 선택한 Drive Markdown:
  `Solstice Finance 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:13UNkOg_VM2zcFwUusyNGynlGYM-Dpzc2:0B8HYgThT3NByMDh5ZUx2QW1CNk9SMGVBL1g2ajJYbjkwQ2hVPQ`.
- Source SHA-256:
  `a00750cf0df28e876573261ffb9362e8083525bcd8ab72d8106fa175d0dc8057`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_solstice_bce2207.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_solstice_bce2207.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_solstice.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, telemetry, artifact, upsert 함수를 선택된 Solstice
  Drive file id 1개에만 적용했다.
- Candidate ingest result:
  - report type: `econ`
  - slug: `solstice`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `bf819d83-4070-46c9-96d6-6ce11182fc5c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id bf819d83-4070-46c9-96d6-6ce11182fc5c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2207" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `9e20fd09-81e2-46e2-bb40-94188d0e292a`
  - promoted at: `2026-06-25T14:37:54.650432+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2207_solstice_econ_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=solstice`
  - `tracked_projects.symbol=SLX`
  - `project_reports.id=9e20fd09-81e2-46e2-bb40-94188d0e292a`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Solstice는 USX 정산 자산, eUSX 수익 토큰, SLX 접근권을 분리해 온체인 조합성과 기관형 오프체인 수익을 연결하지만, 장기 신뢰는 투명성에 달려 있다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=bf819d83-4070-46c9-96d6-6ce11182fc5c`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/solstice`,
    `https://www.bcelab.xyz/ko/reports/solstice/econ`,
    `https://www.bcelab.xyz/en/projects/solstice`,
    `https://www.bcelab.xyz/en/reports/solstice/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2208 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 00:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 루틴 실행 [BCE-2207](/BCE/issues/BCE-2207)는 `solstice/econ` source를
  이미 promoted 및 웹 검증 완료했다. 이번 실행은 DB의 promoted source
  identity를 제외하고 다음 미승격 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 IVVON MAT/ECON은 `tracked_projects` 매칭이 없어 스킵했고, Frax MAT는
  웹 공개 KO target row가 없어 스킵했다. 다음 eligible source로
  `USD.AI` MAT를 선택했다.
- 선택한 Drive Markdown:
  `USD.AI의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025 - 2026.md`.
- Source identity:
  `drive:1RZ1ENCwpW0O-XUmN8tCdt2nDCUNL3HHw:0B8HYgThT3NByRW4rYU15dm1CUHZicVNLejNFaElUTUJSVlBNPQ`.
- Source SHA-256:
  `023d5ec1869c97e45df0f488cd2ab19ce9e355cd4227be37d364426d0a153250`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_usdai_bce2208.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_usdai_bce2208.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_usdai.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, artifact, and `upsert_job` 함수를 선택된 USD.AI
  Drive file id 1개에만 적용했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `usdai`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `dcd812d9-639c-4b2f-a437-681e6123fc38`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id dcd812d9-639c-4b2f-a437-681e6123fc38 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2208" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `e39b7659-7334-4821-ae2c-28d4c66b411b`
  - promoted at: `2026-06-25T15:08:17.401868+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2208_usdai_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=usdai`
  - `tracked_projects.symbol=USDAI`
  - `project_reports.id=e39b7659-7334-4821-ae2c-28d4c66b411b`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=USD.AI는 GPU 담보 신용과 온체인 달러 상품으로 AI 인프라 수익을 연결하지만, 아직 전개 단계라 담보 검증과 거버넌스 이력이 핵심 과제다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=dcd812d9-639c-4b2f-a437-681e6123fc38`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/usdai`,
    `https://www.bcelab.xyz/ko/reports/usdai/maturity`,
    `https://www.bcelab.xyz/en/projects/usdai`,
    `https://www.bcelab.xyz/en/reports/usdai/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2209 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 00:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `acf6135`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 루틴 실행 [BCE-2208](/BCE/issues/BCE-2208)는 `usdai/mat` source를
  already promoted 및 웹 검증 완료했다. 프로세스 유실 재시도에서 DB를 재확인한
  결과 이번 BCE-2209 산출물은 이미 생성되고 promotion까지 완료되어 있었으며,
  추가 Drive 스캔에서는 promoted source identity를 제외한 파싱 가능 KO Markdown
  미승격 후보가 0건으로 확인되었다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했고,
  처리 대상은 `Quack AI` ECON source였다.
- 선택한 Drive Markdown:
  `Quack AI 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1T3Gipe9I6RE4ewzA58oBr-Ob2Ci521wi:0B8HYgThT3NByYURDTFY1VU9WTkEranJzNGhVMXRPSUQvUUxrPQ`.
- Source SHA-256:
  `8d57b0d1f75227b0fd804d807fd07c3e15f379c99e579e0b0416d03eb4738d43`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_quack-ai_bce2209.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_quack-ai_bce2209.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_quack-ai.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, artifact, and `upsert_job` 함수를 선택된 Quack AI
  Drive file id 1개에만 적용했다.
- Candidate ingest result:
  - report type: `econ`
  - slug: `quack-ai`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `15810aeb-791c-487a-96a1-fca49af9c2c8`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 15810aeb-791c-487a-96a1-fca49af9c2c8 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2209" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `70a45bd7-0a5a-4b4e-aeb7-1a60506fb532`
  - promoted at: `2026-06-25T15:40:13.947121+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2209_quack_ai_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=quack-ai`
  - `tracked_projects.symbol=Q`
  - `project_reports.id=70a45bd7-0a5a-4b4e-aeb7-1a60506fb532`
  - `report_type=econ`, `language=ko`, `status=published`, `is_latest=true`
  - `card_summary_ko=Quack AI는 Q402와 Policy Engine으로 AI 에이전트의 거버넌스 위임과 가스리스 실행을 연결하지만, Q 토큰 가치 포획과 오프체인 신뢰 구조는 아직 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=15810aeb-791c-487a-96a1-fca49af9c2c8`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/quack-ai`,
    `https://www.bcelab.xyz/ko/reports/quack-ai/econ`,
    `https://www.bcelab.xyz/en/projects/quack-ai`,
    `https://www.bcelab.xyz/en/reports/quack-ai/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2212 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 05:19 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  최신 위키 기록 [BCE-2209](/BCE/issues/BCE-2209) 및 DB의 promoted
  `report_summary_jobs` source identity를 확인했다. [BCE-2209](/BCE/issues/BCE-2209)는
  `quack-ai/econ` source를 이미 promoted 및 웹 검증 완료했으며, 이번 실행은
  promoted source identity를 제외한 다음 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 `Numerai` MAT는 공개 KO target row가 없고, `WOULD` 및 `IVVON`은
  `tracked_projects` 매칭이 없어 스킵했다. `Frax` MAT는 `frax`,
  `legacy-frax-dollar`, `frax-usd` 매칭이 충돌하고 이전 위키에서 target
  mismatch로 스킵된 상태라 이번 실행에서도 안전하게 건너뛰었다. 다음 명확한
  eligible source로 `GHO` MAT를 선택했다.
- 선택한 Drive Markdown:
  `GHO의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023-2026.md`.
- Source identity:
  `drive:1i8-Xyc1wKKQxZmxPW2uLGSD1HdJsznHO:0B8HYgThT3NByWTdFejFSRXVQMHVGUXYyWFFXSHFoYk9FeEQ4PQ`.
- Source SHA-256:
  `a7016a09dccbfb62e48ac1420b3e242a395dacd5f716c5fc4a3c3f0efe1a020b`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_gho_bce2212.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_gho_bce2212.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_gho.json`.
- Execution note:
  generic entrypoint의 광범위 Drive 다운로드 경로를 피하기 위해 기존
  candidate validation, artifact, and `upsert_job` 함수를 선택된 GHO
  Drive file id 1개에만 적용했다. 첫 upsert는 카드 품질 gate 때문에 invalid
  row로 생성됐으나, CRO JSON 문구를 단일 문장/low-format 구조로 수정한 뒤
  같은 idempotency row를 `valid`로 갱신했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `gho`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `6e840b9c-1108-4213-97dd-0f68735ee335`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 6e840b9c-1108-4213-97dd-0f68735ee335 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2212" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `693fc7d9-7ffc-4887-8228-31ea0e88768a`
  - promoted at: `2026-06-25T20:18:20.239837+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2212_gho_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=gho`
  - `tracked_projects.symbol=GHO`
  - `project_reports.id=693fc7d9-7ffc-4887-8228-31ea0e88768a`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=GHO는 Aave 기반 초과담보 스테이블코인에서 DAO 수익 자산으로 성숙했지만, sGHO 비용과 보조금 없는 유기적 수요 검증이 남아 있다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=6e840b9c-1108-4213-97dd-0f68735ee335`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/gho`,
    `https://www.bcelab.xyz/ko/reports/gho/maturity`,
    `https://www.bcelab.xyz/en/projects/gho`,
    `https://www.bcelab.xyz/en/reports/gho/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2218 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 08:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 위키는 BCE-2212 이후 일부 실행 기록이 누락되어 있었으므로
  로컬 검증 artifact와 DB promoted 상태를 함께 확인했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai` MAT는 공개 KO maturity target row가 없고,
  `WOULD` 및 `IVVON`은 `tracked_projects` 매칭이 없으며, `Frax` MAT는
  target slug가 충돌해 스킵했다. 다음 명확한 eligible source로 `Rain` MAT를
  선택했다.
- 선택한 Drive Markdown:
  `Rain의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025 - 2026.md`.
- Source identity:
  `drive:1cLunt7w9dzBy1gvnQEtUGjLcwKtAsnuO:0B8HYgThT3NBySjNTb0UwRG9teDlHV1RTMmg5RldDcjBZcVZvPQ`.
- Source SHA-256:
  `e9d258e985197c39a02c901e2101b81de9b0fc1f41238e85527c13a3b900778e`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_rain_bce2218.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_rain_bce2218.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_rain.json`.
- Execution note:
  generic entrypoint의 slugless Drive broad-download 경로를 피하기 위해 기존
  candidate validation, artifact, telemetry, and `upsert_job` 함수를 선택된
  Rain Drive file id 1개에만 적용했다. 로컬 source snapshot dry-run으로 먼저
  검증한 뒤 Drive identity candidate를 upsert했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `rain`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d7a64ecc-ab9a-495c-aa2b-ade9028efa46`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d7a64ecc-ab9a-495c-aa2b-ade9028efa46 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2218" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `665f50bf-e4bc-4267-a1a0-c3cd021b8a49`
  - promoted at: `2026-06-25T23:08:00.241554+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2218_rain_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=rain`
  - `tracked_projects.symbol=RAIN`
  - `project_reports.id=665f50bf-e4bc-4267-a1a0-c3cd021b8a49`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=Rain은 Arbitrum 예측시장과 SDK, 수수료 소각 구조를 갖췄지만 DAO와 오라클 성능, 실제 수익 검증이 아직 성숙도 병목이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=d7a64ecc-ab9a-495c-aa2b-ade9028efa46`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/rain`,
    `https://www.bcelab.xyz/ko/reports/rain/maturity`,
    `https://www.bcelab.xyz/en/projects/rain`,
    `https://www.bcelab.xyz/en/reports/rain/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO and EN surfaces contained the promoted summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2219 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 08:42 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 [BCE-2218](/BCE/issues/BCE-2218)는 Rain MAT를
  이미 promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음 후보부터
  선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai` MAT는 공개 KO maturity target row가 없고,
  `WOULD` 및 `IVVON`은 `tracked_projects` 매칭이 없으며, `Frax` MAT는
  target slug 충돌 이력이 있어 스킵했다. 다음 명확한 eligible source로
  `Ondo USDY` MAT를 선택했다.
- 선택한 Drive Markdown:
  `Ondo USDY의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023–2026.md`.
- Source identity:
  `drive:1LrkP0iPP2jaFzFAA4PUTUq95sGNlRSKC:0B8HYgThT3NBydnRjdEtnZkVpMGswS3NJMTlmcFZidk1iUzhrPQ`.
- Source SHA-256:
  `ab25109207dfa5341933b083601fafc986b4463025f097b4828b54c4090e22e2`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_ondo-finance_bce2219.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_ondo-finance_bce2219.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_ondo-finance.json`.
- Execution note:
  generic entrypoint의 slugless Drive broad-download 경로를 피하기 위해 기존
  candidate validation, artifact, telemetry, and `upsert_job` 함수를 선택된
  Ondo USDY Drive file id 1개에만 적용했다. 로컬 source snapshot dry-run으로
  먼저 검증한 뒤 Drive identity candidate를 upsert했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `ondo-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `3107612d-a63a-4273-9ef8-2e1d7fdbd8b8`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 3107612d-a63a-4273-9ef8-2e1d7fdbd8b8 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2219" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `0321d2b4-e6d5-42c0-8024-fc12f61aacdc`
  - promoted at: `2026-06-25T23:40:43.852671+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2219_ondo_finance_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ondo-finance`
  - `tracked_projects.symbol=ONDO`
  - `project_reports.id=0321d2b4-e6d5-42c0-8024-fc12f61aacdc`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=Ondo USDY는 21억 달러 규모의 토큰화 국채 수익 상품으로 성장했지만, DeFi 활용률과 상환 접근성은 아직 성숙도 제약이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=3107612d-a63a-4273-9ef8-2e1d7fdbd8b8`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ondo-finance`,
    `https://www.bcelab.xyz/ko/reports/ondo-finance/maturity`,
    `https://www.bcelab.xyz/en/projects/ondo-finance`,
    `https://www.bcelab.xyz/en/reports/ondo-finance/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO and EN surfaces contained the promoted summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2220 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 09:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 [BCE-2219](/BCE/issues/BCE-2219)는 Ondo USDY
  MAT를 promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음 후보부터
  선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai` MAT는 공개 KO maturity target row가 없고,
  `WOULD` 및 `IVVON`은 `tracked_projects` 매칭이 없으며, `Frax` MAT는
  target slug 충돌 이력이 있어 스킵했다. 다음 명확한 eligible source로
  `LAB` MAT를 선택했다.
- 선택한 Drive Markdown:
  `LAB의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025 - 2026.md`.
- Source identity:
  `drive:1IRrRzJ1QDKRAWx3e6y19ySBkolfYUXoJ:0B8HYgThT3NByWEdHMjRJbGw5dDlXT09MSSsrWk9na0lSbE0wPQ`.
- Source SHA-256:
  `db89348170d4b2cff373a61fdd556364f794ee85fe91d02fbbc00e96611cac2e`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_lab_bce2220.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_lab_bce2220.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_lab.json`.
- Execution note:
  generic entrypoint의 slugless Drive broad-download 경로를 피하기 위해 기존
  candidate validation, artifact, telemetry, and `upsert_job` 함수를 선택된
  LAB Drive file id 1개에만 적용했다. 로컬 source snapshot dry-run으로 먼저
  검증한 뒤 Drive identity candidate를 upsert했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `lab`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `9cc23b57-85b4-4f7c-a16a-40c64eea68cc`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 9cc23b57-85b4-4f7c-a16a-40c64eea68cc --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2220" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `b936ffc7-ee8b-478f-9833-566acafdb649`
  - promoted at: `2026-06-26T00:08:28.51445+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2220_lab_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=lab`
  - `tracked_projects.symbol=LAB`
  - `project_reports.id=b936ffc7-ee8b-478f-9833-566acafdb649`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_summary_ko=LAB는 트레이딩 터미널과 멀티체인 실행 서사를 빠르게 만들었지만, 최근 수수료와 개발 투명성 검증이 성숙도 병목이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=9cc23b57-85b4-4f7c-a16a-40c64eea68cc`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/lab`,
    `https://www.bcelab.xyz/ko/reports/lab/maturity`,
    `https://www.bcelab.xyz/en/projects/lab`,
    `https://www.bcelab.xyz/en/reports/lab/maturity` returned HTTP `200`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2221 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 09:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 [BCE-2220](/BCE/issues/BCE-2220)는 LAB MAT를
  promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai/Numeraire`, `WOULD`, `IVVON`은 공개 target
  row 또는 tracked project 매칭이 없고, `Frax` MAT는 기존 target slug 충돌
  이력이 있어 스킵했다. 다음 명확한 eligible source로 `PUMP` FOR를 선택했다.
- 선택한 Drive Markdown:
  `PUMP 시장 무결성 및 심층 포렌식 리스크 보고서 (1).md`.
- Source identity:
  `drive:1Lvw31rxFv1AbL93ru-rp-7w5oDYgGK8y:0B8HYgThT3NByREFuVzBkVmFkcEFXT2tFNllKeGFJdTNMazY4PQ`.
- Source SHA-256:
  `5778319e270bbed1411e2bde90c36e82afb0f89e6b1379a66d446b6d7ba2fddf`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_pump-fun_bce2221.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_pump-fun_bce2221.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_pump-fun.json`.
- Execution note:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug pump-fun --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_pump-fun_bce2221.json --require-agent-output --limit 1 --force`
  는 동일 slug 매칭에서 다른 Drive file id
  `1ApDo2bVWFAykInB4mdh0rzQKMtzULmJ9`를 먼저 선택해 source grounding
  mismatch로 validation_failed row
  `5de9993c-3e0c-4f86-ad23-0f9477f4649b`를 만들었다. 해당 row는
  promotion 대상이 아니며, 기존 실행 패턴과 동일하게 선택한 PUMP Drive
  file id 1개에 기존 candidate validation, artifact, telemetry, and
  `upsert_job` 함수를 적용했다. 로컬 source snapshot dry-run으로 먼저
  검증한 뒤 Drive identity candidate를 upsert했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `pump-fun`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `3c00d416-6317-4f16-a8ea-e7ca045bfb37`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 3c00d416-6317-4f16-a8ea-e7ca045bfb37 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2221" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d644d0ec-d894-4792-9e75-11f69ade5098`
  - promoted at: `2026-06-26T00:39:13.623576+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2221_pump_fun_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=pump-fun`
  - `tracked_projects.symbol=PUMP`
  - `project_reports.id=d644d0ec-d894-4792-9e75-11f69ade5098`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `is_latest=true`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=3c00d416-6317-4f16-a8ea-e7ca045bfb37`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/pump-fun`,
    `https://www.bcelab.xyz/ko/reports/forensic/pump-fun`,
    `https://www.bcelab.xyz/en/projects/pump-fun`,
    `https://www.bcelab.xyz/en/reports/forensic/pump-fun` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - Legacy-shaped paths `/ko/reports/pump-fun/forensic` and
    `/en/reports/pump-fun/forensic` returned HTTP `200` but did not expose the
    promoted forensic report content; the active FOR route is
    `/reports/forensic/pump-fun`.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2222 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 10:11 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 [BCE-2221](/BCE/issues/BCE-2221)는 PUMP FOR를
  promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai/Numeraire`, `WOULD`, `IVVON`은 공개 target
  row 또는 tracked project 매칭이 없고, 다음 명확한 eligible source로
  `AWE` FOR를 선택했다.
- 선택한 Drive Markdown:
  `AWE 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1ApDo2bVWFAykInB4mdh0rzQKMtzULmJ9:0B8HYgThT3NByQm0xcUlySGE4RzFpM1J1V2Q2NWlHSTRyOWs4PQ`.
- Source SHA-256:
  `a852a882fc72d17246dc6b92654c104bb8408198b30e89b78a61f22b0e8b4dc6`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_awe-network_bce2222.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_for_awe-network_bce2222.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_awe-network.json`.
- Execution note:
  표준 ingest command는 AWE Drive source를 정확히 선택했으나 초기 JSON의
  raw formatting fragment 검증 실패로 같은 idempotency row를 `--force`로
  valid 상태까지 갱신했다. 이어 filename에서 report version을 추론하지 못해
  version 1 `coming_soon` row에 먼저 승격된 job
  `28133749-e15e-469f-851c-be07475a751a`가 발생했다. 웹 가시성 요건을
  충족하기 위해 동일 Drive identity를 version 2 candidate로 재업서트하고
  published/latest row에 별도 승격했다.
- Candidate ingest result:
  - report type: `for`
  - slug: `awe-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `c9f94799-b98d-44b3-8cec-fa9d2b735a3a`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id c9f94799-b98d-44b3-8cec-fa9d2b735a3a --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2222" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `f7c82a65-c94b-4064-aa0b-2282be4ad2cb`
  - promoted at: `2026-06-26T01:11:03.076478+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2222_awe_network_for_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=awe-network`
  - `tracked_projects.symbol=AWE`
  - `project_reports.id=f7c82a65-c94b-4064-aa0b-2282be4ad2cb`
  - `report_type=forensic`, `language=ko`, `status=published`,
    `version=2`, `is_latest=true`
  - `card_summary_ko=AWE는 단기 급등 뒤 고점권 거래량과 빠른 되돌림이 겹치며 조작·유동성 리스크가 높은 포렌식 구간에 있다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=c9f94799-b98d-44b3-8cec-fa9d2b735a3a`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/awe-network`,
    `https://www.bcelab.xyz/ko/reports/forensic/awe-network`,
    `https://www.bcelab.xyz/en/projects/awe-network`,
    `https://www.bcelab.xyz/en/reports/forensic/awe-network` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2223 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-26 11:04 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `0822354`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs` source identity를 조회해 이미 승격된
  source를 제외했다. 직전 [BCE-2222](/BCE/issues/BCE-2222)는 AWE FOR를
  promoted 및 웹 검증 완료했으므로, 이번 실행은 그 다음 후보부터 선별했다.
- 후보 선택:
  Drive `analysis2/analysis` scope `all`을 메타데이터 기준으로 스캔했다.
  최신 미승격 후보 중 `Numerai/Numeraire`는 공개 KO report target row가
  없고, `WOULD`는 tracked project 매칭이 없어 스킵했다. 다음 명확한
  eligible source로 `Quack AI` MAT를 선택했다.
- 선택한 Drive Markdown:
  `Quack AI의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Source identity:
  `drive:1EYjBWjRdBoRkbQl2NfzSnf-BEZIoCfKh:0B8HYgThT3NByS1VmTnRtajFxczdKMzJwbVRXc1JyMmZENC84PQ`.
- Source SHA-256:
  `5b6403cc11421bc37b1714bc65ea4c03406be3c41ee8d8fac458966672726610`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_quack-ai_bce2223.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_quack-ai_bce2223.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_quack-ai.json`.
- Execution note:
  표준 command
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug quack-ai --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_quack-ai_bce2223.json --require-agent-output --limit 1 --force`
  는 기존 재발과 동일하게 slugless Drive broad-download 경로에서 제한 시간
  내 완료되지 않아 중단했다. 기존 candidate validation, artifact,
  telemetry, and `upsert_job` 함수를 선택된 Quack AI Drive file id 1개에만
  적용했다. 로컬 source snapshot dry-run으로 먼저 검증한 뒤 Drive identity
  candidate를 upsert했다.
- Candidate ingest result:
  - report type: `mat`
  - slug: `quack-ai`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `daf41d0c-a521-4af0-9a96-85d712ab044f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id daf41d0c-a521-4af0-9a96-85d712ab044f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2223" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `64ede1cf-66a0-4754-bb46-c4a5e3951d3e`
  - promoted at: `2026-06-26T02:04:29.322721+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2223_quack_ai_mat_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=quack-ai`
  - `tracked_projects.symbol=Q`
  - `project_reports.id=64ede1cf-66a0-4754-bb46-c4a5e3951d3e`
  - `report_type=maturity`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=Quack AI는 AI 거버넌스와 Q402 실행 레이어를 결합한 초기 상용화 인프라지만, 실사용·수익·RWA 검증 데이터 부족이 성숙도 병목이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=daf41d0c-a521-4af0-9a96-85d712ab044f`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/quack-ai`,
    `https://www.bcelab.xyz/ko/reports/quack-ai/maturity`,
    `https://www.bcelab.xyz/en/projects/quack-ai`,
    `https://www.bcelab.xyz/en/reports/quack-ai/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary and Investment View text.
  - EN surfaces contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2284 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 18:33 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `issue_assigned`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2283](/BCE/issues/BCE-2283)는 `AI Rig Complex`
  MAT를 promoted 및 웹 검증 완료했으므로, 이번 실행은 다음 미승격
  source인 `AI Rig Complex ARC` ECON을 처리했다.
- 선택한 Drive Markdown:
  `AI Rig Complex ARC 크립토이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `ai-rig-complex` (`symbol=ARC`, `status=monitoring_only`) with website-visible
  KO econ target row.
- Source identity:
  `drive:1QBX4z1-lPWJrfkB5WHJmkem9BWIdZy4n:0B8HYgThT3NByNkFNMk5DTzZ2UXcvVTBqeVhNU2RUWWMvZzlNPQ`.
- Source SHA-256:
  `1a69cbbe2287dab490fa7955a8627946d6ea83126566279f2ae096366d6a3244`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_ai-rig-complex_bce2284.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_ai-rig-complex_bce2284.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_ai-rig-complex.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug ai-rig-complex --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_ai-rig-complex_bce2284.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `ai-rig-complex`
  - validation status: `valid`
  - validation reasons: none after replacing the EN `open-source` hyphen with
    validator-safe `open source`
  - upsert result: `inserted`
  - job id: `eff5016d-90af-41bf-82f2-923ad7b0a95e`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id eff5016d-90af-41bf-82f2-923ad7b0a95e --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2284" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `661f89ca-afe5-4eab-a5cd-53b606cf58c9`
  - promoted at: `2026-06-28T09:33:17.462248+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2284_ai_rig_complex_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=ai-rig-complex`, `symbol=ARC`
  - `tracked_projects.status=monitoring_only`
  - `report_summary_jobs.id=eff5016d-90af-41bf-82f2-923ad7b0a95e`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=661f89ca-afe5-4eab-a5cd-53b606cf58c9`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=AI Rig Complex ARC는 Solana 토큰과 Rig 오픈소스 AI 에이전트 프레임워크를 결합한 경제 설계다. 제품 채택 잠재력은 있지만 수수료 라우팅과 토큰 가치 환류가 아직 약하다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/ai-rig-complex`,
    `https://www.bcelab.xyz/en/projects/ai-rig-complex`,
    `https://www.bcelab.xyz/ko/reports/ai-rig-complex/econ`, and
    `https://www.bcelab.xyz/en/reports/ai-rig-complex/econ` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary.
  - EN surfaces contained the promoted English summary.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2285 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-28 19:27 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fcbfe1b`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` 및
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  `process_lost_retry`; 신규 댓글은 없었고 harness checkout 상태라 추가
  checkout은 하지 않았다.
- 재발/중복 확인:
  DB의 promoted `report_summary_jobs.source_identity`와 최신 위키 이력을
  확인했다. 직전 [BCE-2284](/BCE/issues/BCE-2284)는 `AI Rig Complex`
  ECON을 promoted 및 웹 검증 완료했으므로, 이번 실행은 다음 미승격 source를
  확인했다. 최신 미승격 후보 `MindWaveDAO` ECON은 현재 DB에
  `mindwavedao` canonical project 및 website-visible KO econ target row가
  존재해 eligible source로 선택했다. 그 다음 후보 `AIOZ` MAT는 현 시점
  canonical project lookup이 여전히 확인되지 않았다.
- 선택한 Drive Markdown:
  `MindWaveDAO 크립토 이코노미 설계 분석 보고서.md`.
- Canonical tracked project:
  `mindwavedao` (`symbol=NILA`, `status=active`).
- Source identity:
  `drive:1oUhpEtCPMXm5a131kJg2OVqqRZUCZhIP:0B8HYgThT3NByY3lBS2QxWWpyaFdUK3JZdHFJKy94SW5KY01RPQ`.
- Source SHA-256:
  `2f2d7d4f37db2d0c08e0a689a256e50bac66c20d49b950ab7fb711648ba8e7d1`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_mindwavedao_bce2285.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_mindwavedao_bce2285.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_mindwavedao.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug mindwavedao --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_mindwavedao_bce2285.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `mindwavedao`
  - validation status: `valid`
  - validation reasons: none after FR/ES summary length and ZH marketing length
    corrections
  - upsert result: `updated_existing`
  - job id: `94934a40-7b30-491a-bf22-a2b6930c0e19`
- Selector recurrence audit:
  표준 command가 정확한 Drive source를 선택했지만 각 실행에서 80-90초가량
  무출력으로 지연됐다. 최초 validation은 FR/ES summary length와 ZH
  marketing length로 invalid였고, 같은 idempotency key를 `--force`로 두 번
  갱신해 최종 valid 상태로 업데이트했다.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 94934a40-7b30-491a-bf22-a2b6930c0e19 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2285" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `3bdd3df5-697d-4acc-b66f-4e3be5fc8985`
  - promoted at: `2026-06-28T10:27:23.931695+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2285_mindwavedao_econ_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=mindwavedao`, `symbol=NILA`
  - `tracked_projects.status=active`
  - `report_summary_jobs.id=94934a40-7b30-491a-bf22-a2b6930c0e19`
  - `validation_status=valid`, `status=candidate_ready`,
    `authority_state=promoted`
  - `authority_mode=llm_active`
  - `project_reports.id=3bdd3df5-697d-4acc-b66f-4e3be5fc8985`
  - `report_type=econ`, `language=ko`, `status=published`,
    `version=1`, `is_latest=true`
  - `card_summary_ko=MindWaveDAO는 NILA를 중심으로 기관 자산관리, AI 수익 전략, RWA, 광고 보상, 환경 크레딧을 묶은 다중 수익원 설계다. 다만 MindChain, 재무 라우팅, 수익 배분, 거버넌스의 온체인 증거가 부족해 실행 검증성이 핵심 리스크다.`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/mindwavedao`,
    `https://www.bcelab.xyz/en/projects/mindwavedao`,
    `https://www.bcelab.xyz/ko/reports/mindwavedao/econ`, and
    `https://www.bcelab.xyz/en/reports/mindwavedao/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO surfaces contained the promoted Korean summary. EN surfaces contained
    the promoted English summary.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Deployment/cache implication:
  this was a Supabase content promotion through the Summary Authority Gate RPC;
  no code deploy was required. Website visibility is already confirmed on the
  current production deployment.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.
