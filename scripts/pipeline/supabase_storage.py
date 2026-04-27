#!/usr/bin/env python3
"""
Supabase Storage helper — BCE-1085

Thin wrapper around supabase-py Storage API for the slide pipeline.
Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from env (the repo-wide standard;
see gdrive_storage.py / ingest_for.py / pipeline_state.py).

Usage:
    client = get_supabase_storage_client()
    ensure_bucket(client, 'slides', public=True)
    public_url = upload_html(client, 'slides', 'econ/foo/latest/ko.html', html_bytes)
"""
from __future__ import annotations

import os
from typing import Optional


def _env(*names: str) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def get_supabase_storage_client():
    """Create a Supabase client for Storage operations.

    Uses SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) + SUPABASE_SERVICE_KEY
    (repo-wide standard). Falls back to NEXT_PUBLIC_SUPABASE_ANON_KEY only as
    a last resort — anon writes will fail at the bucket policy layer.
    Raises RuntimeError on missing config.
    """
    url = _env('SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_URL')
    key = _env('SUPABASE_SERVICE_KEY', 'NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_KEY is not set")

    from supabase import create_client
    return create_client(url, key)


def ensure_bucket(client, name: str = 'slides', public: bool = True) -> None:
    """Idempotently create a Storage bucket. No-op if it already exists."""
    try:
        existing = client.storage.list_buckets()
    except Exception as e:
        raise RuntimeError(f"Failed to list Supabase Storage buckets: {e}") from e

    def _bucket_name(b):
        if isinstance(b, dict):
            return b.get('name') or b.get('id')
        return getattr(b, 'name', None) or getattr(b, 'id', None)

    if any(_bucket_name(b) == name for b in existing or []):
        return

    try:
        client.storage.create_bucket(name, options={'public': public})
    except Exception as e:
        msg = str(e)
        if 'already exists' in msg.lower() or 'duplicate' in msg.lower():
            return
        raise RuntimeError(f"Failed to create bucket '{name}': {e}") from e


def upload_html(
    client,
    bucket: str,
    key: str,
    content: bytes,
    content_type: str = 'text/html; charset=utf-8',
    upsert: bool = True,
) -> str:
    """Upload an HTML blob and return its public URL.

    `key` is the in-bucket object path (e.g. 'econ/foo/latest/ko.html').
    """
    if isinstance(content, str):
        content = content.encode('utf-8')

    file_options = {
        'content-type': content_type,
        'cache-control': 'public, max-age=300',
        'upsert': 'true' if upsert else 'false',
    }

    storage = client.storage.from_(bucket)
    try:
        storage.upload(path=key, file=content, file_options=file_options)
    except Exception as e:
        msg = str(e)
        # Older supabase-py raises on existing object even with upsert=true; retry via update.
        if upsert and ('Duplicate' in msg or 'already exists' in msg.lower() or '409' in msg):
            try:
                storage.update(path=key, file=content, file_options=file_options)
            except Exception as e2:
                raise RuntimeError(f"Storage upsert failed for {bucket}/{key}: {e2}") from e2
        else:
            raise RuntimeError(f"Storage upload failed for {bucket}/{key}: {e}") from e

    res = storage.get_public_url(key)
    if isinstance(res, dict):
        url = (res.get('data') or {}).get('publicUrl') or res.get('publicUrl') or res.get('publicURL')
    else:
        url = res
    if not url:
        raise RuntimeError(f"Could not resolve public URL for {bucket}/{key}")
    # Some SDK versions append a trailing '?' — strip it for cleanliness.
    return url.rstrip('?')
