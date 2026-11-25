"""Prepare a Maven seed from the exact Batch 01 hosted transfer."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile

from engineering.dependency_resolution.inputs import file_hash, require, verify_tree

ARCHIVE = '1bd9066b0dcfdadf7cc3b869910d38a639c07fb4106c6fb7e10b8b039b6f0ad4'
PRODUCER = '792f7f23a44ca6309977c395dc98938645036071'
LOCK = Path('engineering/dependency_resolution/maven-artifacts.lock.json')


def restore(archive, destination, artifacts):
    with zipfile.ZipFile(archive) as source:
        files = [entry for entry in source.infolist() if not entry.is_dir()]
        require(len(files) == len(artifacts) and {entry.filename for entry in files} == set(artifacts),
                'MAVEN_TRANSFER_INVENTORY')
        for entry in files:
            path = Path(entry.filename)
            require(not path.is_absolute() and '..' not in path.parts and '\\' not in entry.filename
                    and not stat.S_ISLNK(entry.external_attr >> 16), 'MAVEN_TRANSFER_PATH')
            require(entry.file_size == artifacts[entry.filename]['size'], 'MAVEN_TRANSFER_SIZE')
        destination.mkdir(mode=0o700, exist_ok=False)
        for entry in files:
            content = source.read(entry)
            require(hashlib.sha256(content).hexdigest() == artifacts[entry.filename]['sha256'],
                    'MAVEN_TRANSFER_CONTENT')
            target = destination / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(content)
    verify_tree(destination, artifacts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    require(file_hash(args.archive) == ARCHIVE, 'MAVEN_TRANSFER_ARCHIVE')
    restore(args.archive, args.destination, json.loads(LOCK.read_bytes())['artifacts'])
    print(json.dumps({'artifact': 15031660633, 'producerCommit': PRODUCER,
                      'archiveSHA256': ARCHIVE, 'lockSHA256': file_hash(LOCK)}))


if __name__ == '__main__':
    main()
