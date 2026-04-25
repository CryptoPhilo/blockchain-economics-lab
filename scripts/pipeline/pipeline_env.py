#!/usr/bin/env python3
"""Shared pipeline environment bootstrap utilities."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

_BOOTSTRAPPED = False


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_pipeline_relative_path(raw_path: str, pipeline_dir: Path | None = None) -> str:
    """Resolve pipeline-relative path to absolute if needed."""
    if not raw_path:
        return ''
    p = Path(raw_path.strip())
    if p.is_absolute():
        return str(p)
    base = pipeline_dir or Path(__file__).resolve().parent
    return str((base / p).resolve())


def default_gdrive_service_account_path(pipeline_dir: Path | None = None) -> str:
    """Return the conventional pipeline-local service account key path."""
    base = pipeline_dir or Path(__file__).resolve().parent
    return str((base / '.gdrive_service_account.json').resolve())


def _read_service_account_project_id(path: str) -> str:
    if not path:
        return ''
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return ''
    project_id = payload.get('project_id')
    return str(project_id).strip() if project_id else ''


def bootstrap_environment(pipeline_dir: Path | None = None) -> Dict[str, str]:
    """
    Load pipeline env files and normalize TLS + GDrive env vars.

    - loads <repo>/.env.local
    - loads scripts/pipeline/.env
    - sets SSL_CERT_FILE / REQUESTS_CA_BUNDLE from certifi when available
    - normalizes relative GDRIVE_SERVICE_ACCOUNT_FILE to pipeline absolute path
    - falls back to scripts/pipeline/.gdrive_service_account.json when present
    - bootstraps Cloud Translation credential/project env with explicit env priority
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return {'status': 'already_bootstrapped'}

    base = pipeline_dir or Path(__file__).resolve().parent
    repo_root = base.parent.parent

    _load_env_file(repo_root / '.env.local')
    _load_env_file(base / '.env')

    try:
        import certifi

        cert_path = certifi.where()
        os.environ.setdefault('SSL_CERT_FILE', cert_path)
        os.environ.setdefault('REQUESTS_CA_BUNDLE', cert_path)
    except Exception:
        pass

    sa_file = os.environ.get('GDRIVE_SERVICE_ACCOUNT_FILE', '').strip()
    if sa_file:
        os.environ['GDRIVE_SERVICE_ACCOUNT_FILE'] = resolve_pipeline_relative_path(sa_file, base)
    else:
        default_sa = Path(default_gdrive_service_account_path(base))
        if default_sa.exists():
            os.environ.setdefault('GDRIVE_SERVICE_ACCOUNT_FILE', str(default_sa))

    translate_credentials_file = os.environ.get('GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_FILE', '').strip()
    if translate_credentials_file:
        translate_credentials_file = resolve_pipeline_relative_path(translate_credentials_file, base)
        os.environ['GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_FILE'] = translate_credentials_file
    else:
        translate_credentials_file = os.environ.get('GDRIVE_SERVICE_ACCOUNT_FILE', '').strip()
        if translate_credentials_file:
            os.environ.setdefault('GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_FILE', translate_credentials_file)

    google_application_credentials = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '').strip()
    if google_application_credentials:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = resolve_pipeline_relative_path(
            google_application_credentials,
            base,
        )
    elif translate_credentials_file:
        os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', translate_credentials_file)

    if not os.environ.get('GOOGLE_CLOUD_TRANSLATE_PROJECT_ID', '').strip():
        inferred_project_id = (
            os.environ.get('GOOGLE_CLOUD_PROJECT', '').strip()
            or os.environ.get('GOOGLE_PROJECT_ID', '').strip()
            or os.environ.get('GCLOUD_PROJECT', '').strip()
            or _read_service_account_project_id(translate_credentials_file)
        )
        if inferred_project_id:
            os.environ.setdefault('GOOGLE_CLOUD_TRANSLATE_PROJECT_ID', inferred_project_id)

    os.environ.setdefault('GOOGLE_CLOUD_TRANSLATE_LOCATION', 'global')

    _BOOTSTRAPPED = True
    return {
        'status': 'bootstrapped',
        'pipeline_dir': str(base),
        'repo_root': str(repo_root),
    }
