#!/usr/bin/env python3
"""
Supabase Storage helper — BCE-1085

Thin wrapper around supabase-py Storage API for the slide pipeline.
Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from env, matching the repo-wide
runtime convention.

Usage:
    client = get_supabase_storage_client()
    ensure_bucket(client, 'slides', public=True)
    public_url = upload_html(client, 'slides', 'econ/foo/latest/ko.html', html_bytes)
"""
from __future__ import annotations

import os
from typing import Optional


SLIDE_BUCKET_ALLOWED_MIME_TYPES = [
    'text/html',
    'image/png',
    'image/jpeg',
    'image/webp',
    'application/pdf',
]


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


def _bucket_name(b):
    if isinstance(b, dict):
        return b.get('name') or b.get('id')
    return getattr(b, 'name', None) or getattr(b, 'id', None)


def _bucket_options(public: bool) -> dict:
    return {
        'public': public,
        'allowed_mime_types': SLIDE_BUCKET_ALLOWED_MIME_TYPES,
    }


def _bucket_allows_slide_assets(bucket) -> bool:
    if isinstance(bucket, dict):
        allowed = (
            bucket.get('allowed_mime_types')
            or bucket.get('allowedMimeTypes')
            or bucket.get('allowed_mimeTypes')
        )
    else:
        allowed = (
            getattr(bucket, 'allowed_mime_types', None)
            or getattr(bucket, 'allowedMimeTypes', None)
            or getattr(bucket, 'allowed_mimeTypes', None)
        )

    if not allowed:
        return False
    return set(SLIDE_BUCKET_ALLOWED_MIME_TYPES).issubset(set(allowed))


def _update_bucket(client, name: str, public: bool) -> None:
    try:
        client.storage.update_bucket(name, options=_bucket_options(public))
    except Exception as e:
        raise RuntimeError(
            f"Failed to update bucket '{name}' MIME policy for slide assets: {e}"
        ) from e


def ensure_bucket(client, name: str = 'slides', public: bool = True) -> None:
    """Idempotently create or repair the Storage bucket used by slide assets."""
    try:
        existing = client.storage.list_buckets()
    except Exception as e:
        raise RuntimeError(f"Failed to list Supabase Storage buckets: {e}") from e

    bucket = next((b for b in existing or [] if _bucket_name(b) == name), None)
    if bucket is not None:
        # Existing production buckets can predate the external page-image
        # fallback and allow only HTML. Repair them before the first upload so
        # 413 fallback assets do not fail halfway through a backfill.
        if not _bucket_allows_slide_assets(bucket):
            _update_bucket(client, name, public)
        return

    try:
        client.storage.create_bucket(name, options=_bucket_options(public))
    except Exception as e:
        msg = str(e)
        if 'already exists' in msg.lower() or 'duplicate' in msg.lower():
            _update_bucket(client, name, public)
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
        # storage3 prepends 'max-age=' to whatever we send here; pass the bare
        # seconds so we end up with 'max-age=300' instead of the previous
        # mangled 'max-age=public, max-age=300' on the object metadata.
        'cache-control': '300',
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
