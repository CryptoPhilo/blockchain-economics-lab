"""
Shared Google Drive draft-ingest helpers.

Provides a common path for BCE Lab markdown draft ingestion across report
types. Folder lookup is case-insensitive and prefers the canonical
`drafts/{TYPE}` uppercase layout.
"""
from __future__ import annotations

from typing import Any


def canonical_draft_folder_name(report_type: str) -> str:
    return report_type.strip().upper()


def find_or_create_folder(drive, name: str, parent_id: str) -> str:
    """Find a subfolder by name under parent, falling back to case-insensitive match."""
    q = (f"'{parent_id}' in parents and name='{name}' "
         f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
    results = drive.files().list(q=q, fields='files(id,name)', spaces='drive').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']

    q_all = (f"'{parent_id}' in parents "
             f"and mimeType='application/vnd.google-apps.folder' and trashed=false")
    results_all = drive.files().list(
        q=q_all, fields='files(id,name)', spaces='drive'
    ).execute()
    for entry in results_all.get('files', []):
        if entry['name'].lower() == name.lower():
            return entry['id']

    meta = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    folder = drive.files().create(body=meta, fields='id').execute()
    return folder['id']


def ensure_drafts_type_folder(drive, root_folder_id: str, report_type: str) -> str:
    """Ensure drafts/{TYPE} exists and return the folder id."""
    drafts_id = find_or_create_folder(drive, 'drafts', root_folder_id)
    type_folder = canonical_draft_folder_name(report_type)
    return find_or_create_folder(drive, type_folder, drafts_id)


def scan_markdown_drafts(drive, folder_id: str) -> list[dict[str, Any]]:
    """Find markdown-like files plus Google Docs exports in a drafts folder."""
    q_md = (f"'{folder_id}' in parents and mimeType='text/markdown' and trashed=false")
    results_md = drive.files().list(
        q=q_md,
        fields='files(id,name,size,modifiedTime,mimeType)',
        pageSize=100,
        orderBy='modifiedTime desc',
    ).execute()
    docs = results_md.get('files', [])
    seen_ids = {doc['id'] for doc in docs}

    q_named_md = (f"'{folder_id}' in parents and name contains '.md' and trashed=false")
    results_named_md = drive.files().list(
        q=q_named_md,
        fields='files(id,name,size,modifiedTime,mimeType)',
        pageSize=100,
        orderBy='modifiedTime desc',
    ).execute()
    for doc in results_named_md.get('files', []):
        if doc['id'] not in seen_ids:
            docs.append(doc)
            seen_ids.add(doc['id'])

    q_gdocs = (f"'{folder_id}' in parents "
               f"and mimeType='application/vnd.google-apps.document' and trashed=false")
    results_gdocs = drive.files().list(
        q=q_gdocs,
        fields='files(id,name,size,modifiedTime,mimeType)',
        pageSize=100,
        orderBy='modifiedTime desc',
    ).execute()
    for doc in results_gdocs.get('files', []):
        if doc['id'] in seen_ids:
            continue
        doc['_gdoc'] = True
        if not doc['name'].endswith('.md'):
            doc['name'] = f"{doc['name']}.md"
        docs.append(doc)
        seen_ids.add(doc['id'])

    return docs


def download_markdown_text(drive, file_id: str, is_gdoc: bool = False) -> str:
    """Download markdown content from Drive, exporting Google Docs when needed."""
    if is_gdoc:
        content = drive.files().export(fileId=file_id, mimeType='text/plain').execute()
        if isinstance(content, str):
            content = content.encode('utf-8')
    else:
        content = drive.files().get_media(fileId=file_id).execute()
    return content.decode('utf-8')
