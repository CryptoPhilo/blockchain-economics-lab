create table if not exists public.drive_file_index (
  file_id text primary key,
  folder_scope text not null,
  source_root text not null,
  report_type text not null check (report_type in ('econ', 'mat', 'for')),
  folder_id text,
  path text not null,
  name text not null,
  mime_type text not null,
  modified_time timestamptz,
  revision_id text,
  size bigint,
  trashed boolean not null default false,
  last_seen_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists drive_file_index_scope_idx
  on public.drive_file_index (report_type, folder_scope, source_root, modified_time desc);

create table if not exists public.drive_file_content_index (
  file_id text not null references public.drive_file_index(file_id) on delete cascade,
  revision_id text not null,
  text_sha256 text,
  extraction_status text not null check (extraction_status in ('pending', 'extracted', 'failed', 'skipped')),
  page_count integer,
  extracted_text_path text,
  error text,
  extracted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (file_id, revision_id)
);

create index if not exists drive_file_content_index_status_idx
  on public.drive_file_content_index (extraction_status, extracted_at desc);

create table if not exists public.analysis_source_map (
  file_id text not null references public.drive_file_index(file_id) on delete cascade,
  revision_id text not null,
  report_type text not null check (report_type in ('econ', 'mat', 'for')),
  project_slug text,
  subject text,
  mapping_confidence integer not null default 0,
  mapping_status text not null check (mapping_status in ('safe', 'ambiguous', 'unmatched', 'skipped')),
  mapping_evidence jsonb not null default '{}'::jsonb,
  mapped_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (file_id, revision_id, report_type)
);

create index if not exists analysis_source_map_selection_idx
  on public.analysis_source_map (report_type, mapping_status, project_slug);

create table if not exists public.drive_source_sync_state (
  source_root text not null,
  folder_scope text not null,
  report_type text not null check (report_type in ('econ', 'mat', 'for')),
  folder_id text not null,
  last_sync_at timestamptz,
  last_success_at timestamptz,
  last_seen_count integer not null default 0,
  last_changed_count integer not null default 0,
  cursor_token text,
  updated_at timestamptz not null default now(),
  primary key (source_root, folder_scope, report_type, folder_id)
);
