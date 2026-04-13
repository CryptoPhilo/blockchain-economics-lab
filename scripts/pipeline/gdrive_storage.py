"""
Google Drive Storage Module — BCE Lab Report Delivery (v2)
Handles file upload, version management, and Supabase metadata recording.

Architecture (v2 — Hybrid Version Management):
    ┌──────────────────────────────────────────────────────────┐
    │  Google Drive                                            │
    │    BCE Lab Reports/                                      │
    │    └── uniswap/                                          │
    │        └── econ/                                         │
    │            ├── uniswap_econ_v1_en.md  ← file_id_A       │
    │            ├── uniswap_econ_v2_en.md  ← file_id_B       │
    │            └── uniswap_econ_v3_en.md  ← file_id_C       │
    │                                                          │
    │  Same-version regeneration → Drive revision (in-place)   │
    │  New version → new file with own file_id & URL           │
    └──────────────────────────────────────────────────────────┘
    ┌──────────────────────────────────────────────────────────┐
    │  Supabase                                                │
    │    project_reports     → latest version pointer           │
    │    report_versions     → full version history w/ URLs     │
    └──────────────────────────────────────────────────────────┘

    Frontend can link to any past version via report_versions.gdrive_url.

Authentication:
    Google Drive:
        Set env: GDRIVE_SERVICE_ACCOUNT_FILE, GDRIVE_ROOT_FOLDER_ID
        Optional: GDRIVE_DELEGATE_EMAIL (domain-wide delegation)

    Supabase:
        Set env: SUPABASE_URL, SUPABASE_SERVICE_KEY

Usage:
    from gdrive_storage import GDriveStorage

    gd = GDriveStorage()
    result = gd.upload_report(
        local_path='output/uniswap_econ_v1_en.md',
        project_slug='uniswap',
        report_type='econ',
        version=1,
        lang='en',
        report_id='uuid-of-project-report',     # optional: Supabase recording
        change_summary='Initial methodology integration',
        word_count=6882,
    )
    print(result['url'])  # direct link to this version
"""

import json
import os
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False

try:
    from supabase import create_client, Client as SupabaseClient
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

# ─── Configuration ───────────────────────────────────────────

GDRIVE_ROOT_FOLDER_ID = os.environ.get('GDRIVE_ROOT_FOLDER_ID', '')
GDRIVE_SERVICE_ACCOUNT_FILE = os.environ.get('GDRIVE_SERVICE_ACCOUNT_FILE', '')
GDRIVE_OAUTH_CREDENTIALS = os.environ.get('GDRIVE_OAUTH_CREDENTIALS', '')
GDRIVE_DELEGATE_EMAIL = os.environ.get('GDRIVE_DELEGATE_EMAIL', '')
GDRIVE_TOKEN_FILE = os.environ.get(
    'GDRIVE_TOKEN_FILE',
    str(Path(__file__).parent / '.gdrive_token.json')
)

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

SCOPES = ['https://www.googleapis.com/auth/drive']

# MIME type mapping
MIME_MAP = {
    '.pdf': 'application/pdf',
    '.md': 'text/markdown',
    '.json': 'application/json',
    '.html': 'text/html',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.csv': 'text/csv',
    '.txt': 'text/plain',
}


class GDriveStorage:
    """
    Google Drive storage client for BCE Lab pipeline.
    Manages versioned file uploads and Supabase metadata recording.
    """

    def __init__(
        self,
        root_folder_id: str = None,
        service_account_file: str = None,
        oauth_credentials_file: str = None,
        delegate_email: str = None,
        supabase_url: str = None,
        supabase_key: str = None,
    ):
        self.root_folder_id = root_folder_id or GDRIVE_ROOT_FOLDER_ID
        self._sa_file = service_account_file or GDRIVE_SERVICE_ACCOUNT_FILE
        self._oauth_file = oauth_credentials_file or GDRIVE_OAUTH_CREDENTIALS
        self._delegate_email = delegate_email or GDRIVE_DELEGATE_EMAIL
        self.service = None
        self._connected = False
        self._folder_cache: Dict[str, str] = {}  # path -> folder_id

        # ── Google Drive auth ──
        if not HAS_GDRIVE:
            print("  [GDrive] google-api-python-client not installed.")
        else:
            creds = self._authenticate()
            if creds:
                try:
                    self.service = build('drive', 'v3', credentials=creds)
                    self._connected = True
                except Exception as e:
                    print(f"  [GDrive] Failed to build service: {e}")

        # ── Supabase client ──
        self.supabase: Optional[SupabaseClient] = None
        sb_url = supabase_url or SUPABASE_URL
        sb_key = supabase_key or SUPABASE_SERVICE_KEY
        if HAS_SUPABASE and sb_url and sb_key:
            try:
                self.supabase = create_client(sb_url, sb_key)
            except Exception as e:
                print(f"  [Supabase] Failed to connect: {e}")

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def has_db(self) -> bool:
        return self.supabase is not None

    # ═══════════════════════════════════════════════════════════
    #  AUTHENTICATION
    # ═══════════════════════════════════════════════════════════

    def _authenticate(self):
        """Authenticate using service account or OAuth2."""
        # Option A: Service Account
        if self._sa_file and os.path.exists(self._sa_file):
            try:
                creds = service_account.Credentials.from_service_account_file(
                    self._sa_file, scopes=SCOPES
                )
                if self._delegate_email:
                    creds = creds.with_subject(self._delegate_email)
                    print(f"  [GDrive] Authenticated via service account (delegating to {self._delegate_email})")
                else:
                    print("  [GDrive] Authenticated via service account (no delegation).")
                return creds
            except Exception as e:
                print(f"  [GDrive] Service account auth failed: {e}")

        # Option B: OAuth2
        if self._oauth_file and os.path.exists(self._oauth_file):
            creds = None
            if os.path.exists(GDRIVE_TOKEN_FILE):
                try:
                    creds = Credentials.from_authorized_user_file(GDRIVE_TOKEN_FILE, SCOPES)
                except Exception:
                    pass

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self._oauth_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                with open(GDRIVE_TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())

            if creds and creds.valid:
                print("  [GDrive] Authenticated via OAuth2.")
                return creds

        if not self._sa_file and not self._oauth_file:
            print("  [GDrive] No credentials configured. Set GDRIVE_SERVICE_ACCOUNT_FILE or GDRIVE_OAUTH_CREDENTIALS.")
        return None

    # ═══════════════════════════════════════════════════════════
    #  FOLDER MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def _find_folder(self, name: str, parent_id: str) -> Optional[str]:
        """Find a folder by name within a parent folder."""
        if not self._connected:
            return None
        try:
            query = (
                f"name = '{name}' and "
                f"'{parent_id}' in parents and "
                f"mimeType = 'application/vnd.google-apps.folder' and "
                f"trashed = false"
            )
            result = self.service.files().list(
                q=query, fields='files(id, name)', pageSize=1
            ).execute()
            files = result.get('files', [])
            return files[0]['id'] if files else None
        except Exception:
            return None

    def _create_folder(self, name: str, parent_id: str) -> Optional[str]:
        """Create a folder and return its ID."""
        if not self._connected:
            return None
        try:
            metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id],
            }
            folder = self.service.files().create(
                body=metadata, fields='id'
            ).execute()
            return folder.get('id')
        except Exception as e:
            print(f"  [GDrive] Failed to create folder '{name}': {e}")
            return None

    def ensure_folder_path(self, *path_parts: str) -> Optional[str]:
        """
        Ensure a folder path exists under root, creating as needed.
        Returns the final folder ID.

        Example:
            folder_id = gd.ensure_folder_path('uniswap', 'econ')
            # Creates: BCE Lab Reports / uniswap / econ
        """
        if not self._connected or not self.root_folder_id:
            return None

        cache_key = '/'.join(path_parts)
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        current_id = self.root_folder_id
        for part in path_parts:
            sub_key = '/'.join(path_parts[:path_parts.index(part)+1])
            if sub_key in self._folder_cache:
                current_id = self._folder_cache[sub_key]
                continue

            folder_id = self._find_folder(part, current_id)
            if not folder_id:
                folder_id = self._create_folder(part, current_id)
            if not folder_id:
                return None
            self._folder_cache[sub_key] = folder_id
            current_id = folder_id

        self._folder_cache[cache_key] = current_id
        return current_id

    # ═══════════════════════════════════════════════════════════
    #  FILE UPLOAD (low-level)
    # ═══════════════════════════════════════════════════════════

    def _find_existing_file(self, name: str, folder_id: str) -> Optional[str]:
        """Find an existing file by name in a folder (for in-place update)."""
        try:
            query = (
                f"name = '{name}' and "
                f"'{folder_id}' in parents and "
                f"mimeType != 'application/vnd.google-apps.folder' and "
                f"trashed = false"
            )
            result = self.service.files().list(
                q=query, fields='files(id)', pageSize=1
            ).execute()
            files = result.get('files', [])
            return files[0]['id'] if files else None
        except Exception:
            return None

    def _get_latest_revision_id(self, file_id: str) -> Optional[str]:
        """Get the latest revision ID of a file (after upload/update)."""
        try:
            revisions = self.service.revisions().list(
                fileId=file_id, fields='revisions(id)'
            ).execute()
            rev_list = revisions.get('revisions', [])
            return rev_list[-1]['id'] if rev_list else None
        except Exception:
            return None

    def upload_file(
        self,
        local_path: str,
        folder_id: str,
        filename: str = None,
        make_public: bool = True,
    ) -> Optional[Dict[str, str]]:
        """
        Upload a file to a specific Google Drive folder.
        If a file with the same name exists, updates it in-place (Drive revision).

        Returns:
            Dict with 'id', 'name', 'url', 'download_url', 'is_update', 'revision_id'
            or None on failure
        """
        if not self._connected:
            return None

        path = Path(local_path)
        if not path.exists():
            print(f"  [GDrive] File not found: {local_path}")
            return None

        fname = filename or path.name
        suffix = path.suffix.lower()
        mime_type = MIME_MAP.get(suffix, mimetypes.guess_type(str(path))[0] or 'application/octet-stream')

        try:
            existing = self._find_existing_file(fname, folder_id)
            is_update = existing is not None

            metadata = {'name': fname}
            media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)

            if existing:
                file_result = self.service.files().update(
                    fileId=existing,
                    body=metadata,
                    media_body=media,
                    fields='id, name, webViewLink, webContentLink',
                ).execute()
            else:
                metadata['parents'] = [folder_id]
                file_result = self.service.files().create(
                    body=metadata,
                    media_body=media,
                    fields='id, name, webViewLink, webContentLink',
                ).execute()

            file_id = file_result.get('id')

            # Make publicly readable
            if make_public and file_id:
                try:
                    self.service.permissions().create(
                        fileId=file_id,
                        body={'type': 'anyone', 'role': 'reader'},
                    ).execute()
                except Exception:
                    pass  # May fail on org-restricted drives

            # Get revision ID
            revision_id = self._get_latest_revision_id(file_id)

            return {
                'id': file_id,
                'name': file_result.get('name'),
                'url': file_result.get('webViewLink', f'https://drive.google.com/file/d/{file_id}/view'),
                'download_url': file_result.get('webContentLink', f'https://drive.google.com/uc?id={file_id}&export=download'),
                'is_update': is_update,
                'revision_id': revision_id,
            }

        except Exception as e:
            print(f"  [GDrive] Upload failed for '{fname}': {e}")
            return None

    # ═══════════════════════════════════════════════════════════
    #  HIGH-LEVEL: VERSIONED REPORT UPLOAD
    # ═══════════════════════════════════════════════════════════

    def upload_report(
        self,
        local_path: str,
        project_slug: str,
        report_type: str,
        version: int = 1,
        lang: str = 'en',
        make_public: bool = True,
        # ── Supabase metadata (optional) ──
        report_id: str = None,
        change_summary: str = None,
        word_count: int = None,
        chapter_count: int = None,
        page_count: int = None,
        generator_version: str = None,
        pipeline_metadata: dict = None,
        created_by: str = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a versioned report file and record metadata.

        Version management:
            - Filename includes version: {slug}_{type}_v{ver}_{lang}.{ext}
            - Same version re-upload → in-place update (Drive revision)
            - New version number → new file with unique URL

        Supabase recording (if report_id provided):
            - Inserts/updates report_versions row
            - Updates project_reports to point to latest version

        Returns:
            Dict with 'id', 'name', 'url', 'download_url', 'version',
            'is_update', 'revision_id', 'db_recorded'
        """
        if not self._connected:
            print("  [GDrive] Not connected. Cannot upload report.")
            return None

        # Ensure folder: root / {project_slug} / {report_type}
        folder_id = self.ensure_folder_path(project_slug, report_type)
        if not folder_id:
            print(f"  [GDrive] Failed to create folder path: {project_slug}/{report_type}")
            return None

        # Filename WITH version (each version = separate file for linkability)
        ext = Path(local_path).suffix
        filename = f"{project_slug}_{report_type}_v{version}_{lang}{ext}"

        # Upload (creates new or updates existing same-version file)
        result = self.upload_file(
            local_path=local_path,
            folder_id=folder_id,
            filename=filename,
            make_public=make_public,
        )

        if not result:
            return None

        result['version'] = version
        result['folder_id'] = folder_id
        action = 'Updated' if result.get('is_update') else 'Created'
        print(f"  [GDrive] {action}: {filename} → {result['url']}")

        # ── Supabase recording ──
        result['db_recorded'] = False
        if self.supabase and report_id:
            try:
                self._record_version(
                    report_id=report_id,
                    version=version,
                    lang=lang,
                    gdrive_file_id=result['id'],
                    gdrive_revision_id=result.get('revision_id'),
                    gdrive_url=result['url'],
                    word_count=word_count,
                    chapter_count=chapter_count,
                    page_count=page_count,
                    generator_version=generator_version,
                    pipeline_metadata=pipeline_metadata,
                    change_summary=change_summary,
                    created_by=created_by,
                )
                self._update_master_report(
                    report_id=report_id,
                    version=version,
                    gdrive_file_id=result['id'],
                    gdrive_url=result['url'],
                    gdrive_download_url=result['download_url'],
                    gdrive_folder_id=folder_id,
                    lang=lang,
                )
                result['db_recorded'] = True
                print(f"  [Supabase] Version {version} recorded for report {report_id[:8]}...")
            except Exception as e:
                print(f"  [Supabase] Failed to record version: {e}")

        return result

    # ═══════════════════════════════════════════════════════════
    #  SUPABASE: VERSION RECORDING
    # ═══════════════════════════════════════════════════════════

    def _record_version(
        self,
        report_id: str,
        version: int,
        lang: str,
        gdrive_file_id: str,
        gdrive_revision_id: str = None,
        gdrive_url: str = None,
        word_count: int = None,
        chapter_count: int = None,
        page_count: int = None,
        generator_version: str = None,
        pipeline_metadata: dict = None,
        change_summary: str = None,
        created_by: str = None,
    ):
        """Insert or update a report_versions row."""
        if not self.supabase:
            return

        row = {
            'report_id': report_id,
            'version': version,
            'language': lang,
            'gdrive_file_id': gdrive_file_id,
            'gdrive_revision_id': gdrive_revision_id,
            'gdrive_url': gdrive_url,
            'word_count': word_count,
            'chapter_count': chapter_count,
            'page_count': page_count,
            'generator_version': generator_version,
            'pipeline_metadata': json.dumps(pipeline_metadata) if pipeline_metadata else '{}',
            'change_summary': change_summary,
            'created_by': created_by or 'pipeline',
        }

        # Remove None values (let DB defaults handle them)
        row = {k: v for k, v in row.items() if v is not None}

        # Upsert on (report_id, version, language)
        self.supabase.table('report_versions').upsert(
            row,
            on_conflict='report_id,version,language',
        ).execute()

    def _update_master_report(
        self,
        report_id: str,
        version: int,
        gdrive_file_id: str,
        gdrive_url: str,
        gdrive_download_url: str,
        gdrive_folder_id: str,
        lang: str,
    ):
        """Update project_reports to point to the latest version."""
        if not self.supabase:
            return

        update_data = {
            'version': version,
            'gdrive_file_id': gdrive_file_id,
            'gdrive_url': gdrive_url,
            'gdrive_download_url': gdrive_download_url,
            'gdrive_folder_id': gdrive_folder_id,
            'file_url': gdrive_url,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }

        # Also update the lang-specific URL map
        # First fetch current map
        try:
            current = self.supabase.table('project_reports').select(
                'gdrive_urls_by_lang'
            ).eq('id', report_id).single().execute()

            urls_by_lang = current.data.get('gdrive_urls_by_lang', {}) if current.data else {}
            urls_by_lang[lang] = {
                'file_id': gdrive_file_id,
                'url': gdrive_url,
                'download_url': gdrive_download_url,
                'version': version,
            }
            update_data['gdrive_urls_by_lang'] = urls_by_lang
        except Exception:
            pass  # If fetch fails, just update without the map

        self.supabase.table('project_reports').update(
            update_data
        ).eq('id', report_id).execute()

    # ═══════════════════════════════════════════════════════════
    #  SUPABASE: VERSION HISTORY QUERY (프론트엔드용)
    # ═══════════════════════════════════════════════════════════

    def get_version_history(
        self,
        report_id: str,
        lang: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a report. Used by frontend to show
        past versions with direct links.

        Returns list of dicts sorted by version DESC:
            [
                {
                    'version': 4,
                    'gdrive_url': 'https://drive.google.com/file/d/.../view',
                    'word_count': 6882,
                    'change_summary': '방법론 프레임워크 통합',
                    'created_at': '2026-04-09T...',
                },
                ...
            ]
        """
        if not self.supabase:
            return []

        try:
            query = self.supabase.table('report_versions').select(
                'version, gdrive_file_id, gdrive_url, gdrive_revision_id, '
                'word_count, chapter_count, page_count, language, '
                'generator_version, change_summary, created_at, created_by, '
                'pipeline_metadata'
            ).eq('report_id', report_id).order('version', desc=True)

            if lang:
                query = query.eq('language', lang)

            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"  [Supabase] Failed to fetch version history: {e}")
            return []

    def get_latest_version(self, report_id: str, lang: str = 'en') -> Optional[Dict[str, Any]]:
        """Get the latest version info for a report."""
        history = self.get_version_history(report_id, lang=lang)
        return history[0] if history else None

    # ═══════════════════════════════════════════════════════════
    #  BUNDLE UPLOAD (multi-language)
    # ═══════════════════════════════════════════════════════════

    def upload_report_bundle(
        self,
        files: List[Dict[str, str]],
        project_slug: str,
        report_type: str,
        version: int = 1,
        make_public: bool = True,
        report_id: str = None,
        change_summary: str = None,
        **kwargs,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Upload multiple report files (multi-language bundle).

        Args:
            files: List of dicts with 'path' and 'lang' keys
            project_slug, report_type, version: identifiers
            report_id: Supabase report ID for metadata recording
            change_summary: version change description
        """
        results = {}
        for f in files:
            result = self.upload_report(
                local_path=f['path'],
                project_slug=project_slug,
                report_type=report_type,
                version=version,
                lang=f['lang'],
                make_public=make_public,
                report_id=report_id,
                change_summary=change_summary,
                **kwargs,
            )
            if result:
                results[f['lang']] = result
        return results

    # ═══════════════════════════════════════════════════════════
    #  UTILITY
    # ═══════════════════════════════════════════════════════════

    def list_folder(self, folder_id: str) -> List[Dict[str, str]]:
        """List files in a folder."""
        if not self._connected:
            return []
        try:
            result = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields='files(id, name, mimeType, size, modifiedTime, webViewLink)',
                orderBy='name',
                pageSize=100,
            ).execute()
            return result.get('files', [])
        except Exception:
            return []

    def get_folder_url(self, folder_id: str) -> str:
        """Get browser URL for a folder."""
        return f"https://drive.google.com/drive/folders/{folder_id}"

    def delete_file(self, file_id: str) -> bool:
        """Move a file to trash."""
        if not self._connected:
            return False
        try:
            self.service.files().update(
                fileId=file_id, body={'trashed': True}
            ).execute()
            return True
        except Exception:
            return False


# ─── Convenience singleton ───────────────────────────────────

_gdrive_instance: Optional[GDriveStorage] = None


def get_gdrive() -> GDriveStorage:
    """Get or create the global GDrive storage singleton."""
    global _gdrive_instance
    if _gdrive_instance is None:
        _gdrive_instance = GDriveStorage()
    return _gdrive_instance


if __name__ == '__main__':
    print("GDrive Storage Module v2 — Status Check")
    print(f"  HAS_GDRIVE lib: {HAS_GDRIVE}")
    print(f"  HAS_SUPABASE lib: {HAS_SUPABASE}")
    print(f"  Root folder ID: {'SET' if GDRIVE_ROOT_FOLDER_ID else 'NOT SET'}")
    print(f"  Service account: {'SET' if GDRIVE_SERVICE_ACCOUNT_FILE else 'NOT SET'}")
    print(f"  Supabase URL: {'SET' if SUPABASE_URL else 'NOT SET'}")

    gd = GDriveStorage()
    print(f"  Drive connected: {gd.connected}")
    print(f"  Supabase connected: {gd.has_db}")

    if gd.connected:
        print("\n  Testing folder creation...")
        folder_id = gd.ensure_folder_path('_test', 'econ')
        print(f"  Test folder: {folder_id}")
        if folder_id:
            print(f"  Folder URL: {gd.get_folder_url(folder_id)}")
    else:
        print("\n  To enable Google Drive storage:")
        print("    1. Create a GCP project, enable Drive API")
        print("    2. Create a Service Account and download JSON key")
        print("    3. Share your 'BCE Lab Reports' Drive folder with the service account email")
        print("    4. Set environment variables:")
        print("       export GDRIVE_SERVICE_ACCOUNT_FILE=/path/to/key.json")
        print("       export GDRIVE_ROOT_FOLDER_ID=<your_folder_id>")
        print("       export SUPABASE_URL=<url>")
        print("       export SUPABASE_SERVICE_KEY=<key>")
    print("\nDone.")
