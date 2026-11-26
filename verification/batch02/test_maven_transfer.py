import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from engineering.ci.batch02_maven import restore


class TransferTests(unittest.TestCase):
    def test_exact_inventory_and_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = 'org/example/1/example.jar'
            artifacts = {name: {'size': 4, 'sha256': hashlib.sha256(b'good').hexdigest()}}
            cases = [
                ({name: b'good'}, None),
                ({}, 'MAVEN_TRANSFER_INVENTORY'),
                ({name: b'evil'}, 'MAVEN_TRANSFER_CONTENT'),
                ({name: b'longer'}, 'MAVEN_TRANSFER_SIZE'),
                ({name: b'good', 'unexpected.jar': b'good'}, 'MAVEN_TRANSFER_INVENTORY'),
            ]
            for i, (members, error) in enumerate(cases):
                archive = root / f'{i}.zip'
                dest = root / str(i)
                with zipfile.ZipFile(archive, 'w') as out:
                    for path, content in members.items():
                        out.writestr(path, content)
                with self.subTest(error=error):
                    if error:
                        with self.assertRaisesRegex(ValueError, error):
                            restore(archive, dest, artifacts)
                    else:
                        restore(archive, dest, artifacts)
                        self.assertEqual((dest / name).read_bytes(), b'good')

    def test_producer_metadata_and_expiry(self):
        from engineering.ci.batch02_maven import ARCHIVE, PRODUCER, verify_metadata

        valid = {'id': 15031660633, 'name': 'successor-verified-maven-inputs',
                 'expired': False, 'digest': 'sha256:' + ARCHIVE,
                 'workflow_run': {'id': 45631338502, 'head_sha': PRODUCER,
                                  'head_repository_id': 1371285836, 'repository_id': 1371285836}}
        verify_metadata(valid)
        for change, code in [
            ({'expired': True}, 'MAVEN_TRANSFER_UNAVAILABLE_OR_EXPIRED'),
            ({'expired': None}, 'MAVEN_TRANSFER_UNAVAILABLE_OR_EXPIRED'),
            ({'digest': 'sha256:' + '0' * 64}, 'MAVEN_TRANSFER_METADATA_DIGEST'),
            ({'workflow_run': {**valid['workflow_run'], 'id': 1}}, 'MAVEN_TRANSFER_PRODUCER'),
            ({'workflow_run': None}, 'MAVEN_TRANSFER_PRODUCER'),
        ]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, code):
                verify_metadata(valid | change)
