"""Publication fault tests for the Linux adapter, not target acceptance evidence."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compiler_contracts import ArtifactPlan
from compiler_core import CompilerFault
from filesystem_artifacts import FilesystemArtifactStore, StoreConflict
from test_phase6_foundations import artifact


class MaterializerFaultTests(unittest.TestCase):
    def test_concurrent_stale_writers_publish_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'application'
            store = FilesystemArtifactStore(root)
            store.apply(ArtifactPlan((artifact(),), ()))
            prior = store.inventory()[0]
            def write(text):
                try:
                    FilesystemArtifactStore(root).apply(ArtifactPlan((artifact(text=text, prior=prior),), ()))
                    return 'published'
                except CompilerFault:
                    return 'stale'
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(write, ('first\n', 'second\n')))
            self.assertCountEqual(results, ['published', 'stale'])
            self.assertIn((root / prior.path).read_text(), ('first\n', 'second\n'))

    def test_unknown_insertion_before_publication_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'application'
            store = FilesystemArtifactStore(root)
            store.apply(ArtifactPlan((artifact(),), ()))
            prior = store.inventory()[0]
            def insert(self, phase):
                (root / 'unknown.txt').write_text('external insertion')
            with patch.object(FilesystemArtifactStore, '_checkpoint', insert), self.assertRaises(StoreConflict):
                store.apply(ArtifactPlan((artifact(text='replacement\n', prior=prior),), ()))
            self.assertEqual((root / prior.path).read_text(), 'initial\n')
            self.assertEqual((root / 'unknown.txt').read_text(), 'external insertion')

    def test_root_symlink_swap_cannot_write_outside(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root, outside, saved = parent / 'application', parent / 'outside', parent / 'saved'
            outside.mkdir()
            (outside / 'sentinel').write_text('unchanged')
            store = FilesystemArtifactStore(root)
            store.apply(ArtifactPlan((artifact(),), ()))
            prior = store.inventory()[0]
            def swap(self, phase):
                root.rename(saved)
                root.symlink_to(outside, target_is_directory=True)
            with patch.object(FilesystemArtifactStore, '_checkpoint', swap), self.assertRaises(StoreConflict):
                store.apply(ArtifactPlan((artifact(text='replacement\n', prior=prior),), ()))
            self.assertEqual(list(outside.iterdir()), [outside / 'sentinel'])
            self.assertEqual((saved / prior.path).read_text(), 'initial\n')

    def test_parent_symlink_swap_cannot_redirect_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            parent, saved, outside = base / 'parent', base / 'saved', base / 'outside'
            outside.mkdir()
            store = FilesystemArtifactStore(parent / 'application')
            store.apply(ArtifactPlan((artifact(),), ()))
            prior = store.inventory()[0]
            def swap(self, phase):
                parent.rename(saved)
                parent.symlink_to(outside, target_is_directory=True)
            with patch.object(FilesystemArtifactStore, '_checkpoint', swap), self.assertRaises(StoreConflict):
                store.apply(ArtifactPlan((artifact(text='replacement\n', prior=prior),), ()))
            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual((saved / 'application' / prior.path).read_text(), 'initial\n')

    def test_human_edit_during_staging_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'application'
            extension = 'frontend/src/extensions/custom.ts'
            store = FilesystemArtifactStore(root)
            store.apply(ArtifactPlan((artifact(extension),), ()))
            store.adopt_human(extension)
            def edit(self, phase):
                (root / extension).write_text('human edit\n')
            with patch.object(FilesystemArtifactStore, '_checkpoint', edit), self.assertRaises(StoreConflict):
                store.apply(ArtifactPlan((artifact('new.txt'),), ()))
            self.assertEqual((root / extension).read_text(), 'human edit\n')
            self.assertFalse((root / 'new.txt').exists())

    def test_process_crash_before_publish_preserves_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'application'
            store = FilesystemArtifactStore(root)
            store.apply(ArtifactPlan((artifact(),), ()))
            metadata = (root / store.META).read_bytes()
            script = '''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
from filesystem_artifacts import FilesystemArtifactStore
from compiler_contracts import ArtifactPlan
from test_phase6_foundations import artifact
store = FilesystemArtifactStore(sys.argv[3])
prior = store.inventory()[0]
FilesystemArtifactStore._checkpoint = lambda self, phase: os._exit(79)
store.apply(ArtifactPlan((artifact(text="replacement\\n", prior=prior),), ()))
'''
            tooling = Path(__file__).resolve().parents[1]
            result = subprocess.run([sys.executable, '-c', script, str(tooling), str(tooling / 'tests'), str(root)], timeout=10)
            self.assertEqual(result.returncode, 79)
            self.assertEqual((root / 'backend/example.txt').read_text(), 'initial\n')
            self.assertEqual((root / store.META).read_bytes(), metadata)
            store.apply(ArtifactPlan((artifact('after-crash.txt'),), ()))
            self.assertTrue((root / 'after-crash.txt').is_file())


if __name__ == '__main__':
    unittest.main()
