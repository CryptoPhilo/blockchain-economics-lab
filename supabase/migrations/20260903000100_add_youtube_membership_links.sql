create extension if not exists pgcrypto;

create table if not exists youtube_membership_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  youtube_channel_id text not null,
  youtube_channel_title text,
  youtube_channel_url text,
  verification_code text not null,
  status text not null default 'pending'
    check (status in ('pending', 'active', 'inactive', 'expired', 'error')),
  membership_level_id text,
  membership_level_name text,
  member_since timestamptz,
  last_verified_at timestamptz,
  access_expires_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id),
  unique (youtube_channel_id)
);

alter table youtube_membership_links enable row level security;

create policy "Users can read their own YouTube membership link"
  on youtube_membership_links
  for select
  using (auth.uid() = user_id);

create index if not exists youtube_membership_links_user_status_idx
  on youtube_membership_links (user_id, status, access_expires_at);
