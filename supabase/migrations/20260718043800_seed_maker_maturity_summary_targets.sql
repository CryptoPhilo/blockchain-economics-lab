-- Create missing MakerDAO/Sky maturity report shells required by the
-- Analysis Markdown Summary Authority Gate. The gate promotes validated
-- summary candidates into existing website-visible project_reports rows and
-- must not create report targets implicitly during promotion.

WITH target_project AS (
  SELECT id
  FROM public.tracked_projects
  WHERE id = 'c2a21591-d620-465d-b6e5-13e0e2609db4'::uuid
    AND slug = 'maker'
    AND status = 'active'::project_status
  LIMIT 1
),
target_languages(language, title_en, title_ko, source_identity, source_filename) AS (
  VALUES
    (
      'ko',
      'Sky Protocol (MakerDAO) Maturity Report',
      'Sky Protocol (MakerDAO) 성숙도 평가 보고서',
      'summary-authority-target:maker/maturity/ko/version:1',
      'MakerDAO_Sky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md'
    ),
    (
      'en',
      'Sky Protocol (MakerDAO) Maturity Report',
      'Sky Protocol (MakerDAO) 성숙도 평가 보고서',
      'summary-authority-target:maker/maturity/en/version:1',
      'MakerDAO_Sky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md'
    ),
    (
      'fr',
      'Sky Protocol (MakerDAO) Maturity Report',
      'Sky Protocol (MakerDAO) 성숙도 평가 보고서',
      'summary-authority-target:maker/maturity/fr/version:1',
      'MakerDAO_Sky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md'
    ),
    (
      'es',
      'Sky Protocol (MakerDAO) Maturity Report',
      'Sky Protocol (MakerDAO) 성숙도 평가 보고서',
      'summary-authority-target:maker/maturity/es/version:1',
      'MakerDAO_Sky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md'
    ),
    (
      'de',
      'Sky Protocol (MakerDAO) Maturity Report',
      'Sky Protocol (MakerDAO) 성숙도 평가 보고서',
      'summary-authority-target:maker/maturity/de/version:1',
      'MakerDAO_Sky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md'
    ),
    (
      'ja',
      'Sky Protocol (MakerDAO) Maturity Report',
      'Sky Protocol (MakerDAO) 성숙度 평가 보고서',
      'summary-authority-target:maker/maturity/ja/version:1',
      'MakerDAO_Sky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md'
    ),
    (
      'zh',
      'Sky Protocol (MakerDAO) Maturity Report',
      'Sky Protocol (MakerDAO) 성숙도 평가 보고서',
      'summary-authority-target:maker/maturity/zh/version:1',
      'MakerDAO_Sky의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017-2026.md'
    )
)
INSERT INTO public.project_reports (
  project_id,
  report_type,
  version,
  status,
  language,
  published_at,
  title_en,
  title_ko,
  translation_status,
  file_urls_by_lang,
  gdrive_urls_by_lang,
  slide_html_urls_by_lang,
  card_data,
  is_latest,
  source_identity,
  source_filename,
  created_at,
  updated_at
)
SELECT
  target_project.id,
  'maturity',
  1,
  'coming_soon'::report_status,
  target_languages.language,
  NULL,
  target_languages.title_en,
  target_languages.title_ko,
  jsonb_build_object(target_languages.language, 'coming_soon'),
  '{}'::jsonb,
  '{}'::jsonb,
  '{}'::jsonb,
  jsonb_build_object(
    'report_type', 'maturity',
    'slug', 'maker',
    'summary_authority_target', jsonb_build_object(
      'issue', 'BCE-2872',
      'blocked_issue', 'BCE-2871',
      'job_id', 'df3f4a59-1cec-448d-8a0b-bb3bb1b44365',
      'source_identity', 'drive:15imBpZqlZSlPOtVFrpjHJ5NEIOIVNSGl:0B8HYgThT3NByOGtYcjBHR3hmUjZjMXBnWGxPOWRjd1oxdkl3PQ',
      'drive_file_id', '15imBpZqlZSlPOtVFrpjHJ5NEIOIVNSGl',
      'revision_id', '0B8HYgThT3NByOGtYcjBHR3hmUjZjMXBnWGxPOWRjd1oxdkl3PQ',
      'source_sha256', '9f9267025b9299f8cb405a173b5ba5db0ca683c16dcce04ce7b132d0874845ac',
      'language', target_languages.language,
      'created_for', 'Summary Authority Gate target backfill'
    )
  ),
  true,
  target_languages.source_identity,
  target_languages.source_filename,
  now(),
  now()
FROM target_project
CROSS JOIN target_languages
WHERE NOT EXISTS (
  SELECT 1
  FROM public.project_reports existing
  WHERE existing.project_id = target_project.id
    AND existing.report_type::text = 'maturity'
    AND existing.version = 1
    AND existing.language = target_languages.language
)
ON CONFLICT (project_id, report_type, version, language) DO UPDATE
SET
  status = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status
      THEN 'coming_soon'::report_status
    ELSE public.project_reports.status
  END,
  translation_status = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status
      THEN COALESCE(public.project_reports.translation_status, '{}'::jsonb)
        || jsonb_build_object(EXCLUDED.language, 'coming_soon')
    ELSE public.project_reports.translation_status
  END,
  card_data = COALESCE(public.project_reports.card_data, '{}'::jsonb)
    || jsonb_build_object(
      'summary_authority_target',
      jsonb_build_object(
        'issue', 'BCE-2872',
        'blocked_issue', 'BCE-2871',
        'job_id', 'df3f4a59-1cec-448d-8a0b-bb3bb1b44365',
        'source_identity', 'drive:15imBpZqlZSlPOtVFrpjHJ5NEIOIVNSGl:0B8HYgThT3NByOGtYcjBHR3hmUjZjMXBnWGxPOWRjd1oxdkl3PQ',
        'drive_file_id', '15imBpZqlZSlPOtVFrpjHJ5NEIOIVNSGl',
        'revision_id', '0B8HYgThT3NByOGtYcjBHR3hmUjZjMXBnWGxPOWRjd1oxdkl3PQ',
        'source_sha256', '9f9267025b9299f8cb405a173b5ba5db0ca683c16dcce04ce7b132d0874845ac',
        'language', EXCLUDED.language,
        'created_for', 'Summary Authority Gate target backfill'
      )
    ),
  is_latest = CASE
    WHEN public.project_reports.status = 'cancelled'::report_status THEN true
    ELSE public.project_reports.is_latest
  END,
  source_identity = COALESCE(
    public.project_reports.source_identity,
    EXCLUDED.source_identity
  ),
  source_filename = COALESCE(
    public.project_reports.source_filename,
    EXCLUDED.source_filename
  ),
  updated_at = now();

UPDATE public.tracked_projects target_project
SET
  last_maturity_report_at = COALESCE(
    target_project.last_maturity_report_at,
    report_target.updated_at,
    now()
  ),
  updated_at = now()
FROM public.project_reports report_target
WHERE target_project.id = 'c2a21591-d620-465d-b6e5-13e0e2609db4'::uuid
  AND target_project.slug = 'maker'
  AND report_target.project_id = target_project.id
  AND report_target.report_type::text = 'maturity'
  AND report_target.version = 1
  AND report_target.language = 'ko'
  AND report_target.status IN ('published', 'coming_soon', 'in_review');
