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
