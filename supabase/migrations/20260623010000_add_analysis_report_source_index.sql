alter table public.analysis_source_map
  add column if not exists report_version integer,
  add column if not exists source_language text;

create table if not exists public.analysis_report_source_index (
  file_id text not null references public.drive_file_index(file_id) on delete cascade,
  revision_id text not null,
  report_type text not null check (report_type in ('econ', 'mat', 'for')),
  project_slug text,
  subject text,
  report_version integer,
  source_language text,
  source_identity text not null,
  folder_scope text not null,
  source_root text not null,
  folder_id text,
  path text not null,
  name text not null,
  mime_type text not null,
  modified_time timestamptz,
  size bigint,
  web_view_link text,
  text_sha256 text,
  extraction_status text not null check (extraction_status in ('pending', 'extracted', 'failed', 'skipped')),
  page_count integer,
  extracted_text_path text,
  mapping_confidence integer not null default 0,
  mapping_status text not null check (mapping_status in ('safe', 'ambiguous', 'unmatched', 'skipped')),
  mapping_evidence jsonb not null default '{}'::jsonb,
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (file_id, revision_id, report_type)
);

create unique index if not exists analysis_report_source_index_identity_idx
  on public.analysis_report_source_index (source_identity, report_type);

create index if not exists analysis_report_source_index_backfill_idx
  on public.analysis_report_source_index (
    report_type,
    mapping_status,
    extraction_status,
    project_slug,
    report_version desc,
    modified_time desc
  );

create index if not exists analysis_report_source_index_path_idx
  on public.analysis_report_source_index (source_root, folder_scope, report_type, path);
