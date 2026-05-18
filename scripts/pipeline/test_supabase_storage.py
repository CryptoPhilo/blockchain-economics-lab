import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from supabase_storage import SLIDE_BUCKET_ALLOWED_MIME_TYPES, ensure_bucket


class FakeStorage:
    def __init__(self, buckets):
        self.buckets = buckets
        self.created = []
        self.updated = []

    def list_buckets(self):
        return self.buckets

    def create_bucket(self, name, options):
        self.created.append((name, options))
        self.buckets.append({'id': name, 'name': name, **options})

    def update_bucket(self, name, options):
        self.updated.append((name, options))


class FakeClient:
    def __init__(self, buckets):
        self.storage = FakeStorage(buckets)


class SupabaseStorageTests(unittest.TestCase):
    def test_ensure_bucket_creates_with_slide_asset_mimes(self):
        client = FakeClient([])

        ensure_bucket(client, 'slides', public=True)

        self.assertEqual(len(client.storage.created), 1)
        name, options = client.storage.created[0]
        self.assertEqual(name, 'slides')
        self.assertTrue(options['public'])
        self.assertEqual(options['allowed_mime_types'], SLIDE_BUCKET_ALLOWED_MIME_TYPES)

    def test_ensure_bucket_repairs_existing_html_only_bucket(self):
        client = FakeClient([
            {'id': 'slides', 'name': 'slides', 'allowed_mime_types': ['text/html']},
        ])

        ensure_bucket(client, 'slides', public=True)

        self.assertEqual(client.storage.created, [])
        self.assertEqual(len(client.storage.updated), 1)
        name, options = client.storage.updated[0]
        self.assertEqual(name, 'slides')
        self.assertEqual(options['allowed_mime_types'], SLIDE_BUCKET_ALLOWED_MIME_TYPES)

    def test_ensure_bucket_leaves_current_bucket_unchanged(self):
        client = FakeClient([
            {
                'id': 'slides',
                'name': 'slides',
                'allowed_mime_types': list(SLIDE_BUCKET_ALLOWED_MIME_TYPES),
            },
        ])

        ensure_bucket(client, 'slides', public=True)

        self.assertEqual(client.storage.created, [])
        self.assertEqual(client.storage.updated, [])


if __name__ == '__main__':
    unittest.main()
