"""H9.1 scoped Maven distribution verification; no release authority or host install."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engineering.dependency_resolution.inputs import inventory, require

CONFIG = ROOT / 'engineering/dependency_resolution/maven-distribution.json'
SOURCES = ('engineering/dependency_resolution/maven_toolchain.py',
           'engineering/dependency_resolution/maven-distribution.json',
           '.github/workflows/phase6-v3-offline.yml')
SHA256 = '1f6d9909266510f039f59aa0e13dcd2c66da85f043e56276e41f2918f8bddaff'
SHA512 = '22d31676d5b92ed53308c19ecded3245d0efd0cddfec51ec7bab62f4f13ad70ddddceff8e62940e0e8e2421f3cde8106737f4becec0aa034ffeff2a754e88337'
URL = 'https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.10.0/apache-maven-3.10.0-bin.zip'


def configuration():
    c = json.loads(CONFIG.read_bytes())
    require(c.get('sha256') == SHA256 and c.get('sha512') == SHA512 and
            c.get('url') == URL and c.get('version') == '3.10.0' and len(c['files']) == 113,
            'UNTRUSTED_DISTRIBUTION_REFERENCE')
    return c


def archive_bytes(raw, c):
    require(c.get('sha256') == SHA256 and c.get('sha512') == SHA512, 'UNTRUSTED_DISTRIBUTION_DIGEST')
    require(hashlib.sha256(raw).hexdigest() == SHA256 and
            hashlib.sha512(raw).hexdigest() == SHA512, 'MAVEN_ARCHIVE_SUBSTITUTION')
    return raw


def extract(raw, destination, expected):
    """Caller must authenticate archive bytes first; validate all members before writes."""
    destination = Path(destination)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(len(z.infolist()) <= 256 and sum(i.file_size for i in z.infolist()) < 32 * 1024 * 1024, 'MAVEN_ARCHIVE_LIMIT')
        files = {}; names = set()
        for i in z.infolist():
            p = PurePosixPath(i.filename)
            require(not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and
                    p.parts[0] == 'apache-maven-3.10.0' and i.filename not in names and
                    not stat.S_ISLNK(i.external_attr >> 16), 'MAVEN_ARCHIVE_PATH')
            names.add(i.filename)
            if not i.is_dir():
                key = '/'.join(p.parts[1:]); data = z.read(i)
                files[key] = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
        require(files == expected, 'MAVEN_DISTRIBUTION_CONTENTS')
        destination.mkdir(mode=0o700, exist_ok=False)
        for i in z.infolist():
            if i.is_dir(): continue
            target = destination.joinpath(*PurePosixPath(i.filename).parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as f: f.write(z.read(i))
            target.chmod(0o755 if i.external_attr >> 16 & 0o111 else 0o644)
    require(inventory(destination) == expected, 'MAVEN_DISTRIBUTION_CONTENTS')


def selected(root, expected, path=None):
    root = Path(root)
    require(root.is_absolute() and root == root.resolve() and not root.is_symlink(), 'MAVEN_ROOT_BINDING')
    require(inventory(root) == expected, 'MAVEN_DISTRIBUTION_CONTENTS')
    executable = root / 'bin/mvn'
    found = shutil.which('mvn', path=path)
    require(found is not None and Path(found).absolute() == executable and
            Path(found).resolve() == executable, 'MAVEN_EXECUTABLE_PRECEDENCE')
    return executable


def version(executable):
    value = subprocess.check_output([str(executable), '-version'], stderr=subprocess.STDOUT,
                                    text=True, timeout=30)
    require(value.splitlines()[0].startswith('Apache Maven 3.10.0 ('), 'MAVEN_VERSION')
    return value


def binding():
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        require(commit == os.environ['GITHUB_SHA'], 'MAVEN_EXECUTION_SOURCE')
        for name, pin in hashes.items():
            raw = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=ROOT)
            require(hashlib.sha256(raw).hexdigest() == pin, 'MAVEN_SOURCE_SUBSTITUTION')
    return {'commit': commit, 'sources': hashes}


def verify(root, receipt):
    c = configuration(); r = json.loads(Path(receipt).read_bytes())
    require(r['source'] == binding() and r['root'] == str(root) and
            r['archiveSHA256'] == SHA256 and r['archiveSHA512'] == SHA512 and
            r['files'] == c['files'], 'MAVEN_STALE_OR_MISMATCHED_RECEIPT')
    exe = selected(root, c['files'])
    require(version(exe) == r['versionOutput'], 'MAVEN_TOOLCHAIN_INVENTORY')
    return r


def ambient_observation():
    """Observe this runner, without retroactively attributing it to an earlier job."""
    executable = shutil.which('mvn')
    result = {'executable': executable, 'PATH': os.environ.get('PATH'),
              'JAVA_HOME': os.environ.get('JAVA_HOME')}
    if executable:
        path = Path(executable).absolute(); chain = []
        for _ in range(16):
            if not path.is_symlink(): break
            target = os.readlink(path); chain.append({'path': str(path), 'target': target})
            path = (path.parent / target).absolute() if not os.path.isabs(target) else Path(target)
        else: raise ValueError('AMBIENT_MAVEN_SYMLINK_LOOP')
        result.update(resolvedExecutable=str(Path(executable).resolve()), symlinkChain=chain,
                      versionOutput=subprocess.check_output([executable, '-version'],
                          stderr=subprocess.STDOUT, text=True, timeout=30))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('provision', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'provision':
        require(os.environ.get('GITHUB_ACTIONS') == 'true' and
                args.root.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve()) and
                args.receipt.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve()), 'DISPOSABLE_CI_ONLY')
        require(args.root == args.root.resolve() and args.receipt == args.receipt.resolve(), 'MAVEN_DESTINATION_SYMLINK')
        c = configuration()
        ambient = ambient_observation()
        # No redirect to another publisher; both approved hashes precede extraction/execution.
        with urllib.request.urlopen(URL, timeout=90) as response:
            require(response.url == URL, 'MAVEN_ACQUISITION_SOURCE')
            raw = response.read(16 * 1024 * 1024 + 1)
        archive_bytes(raw, c)
        extract(raw, args.root, c['files'])
        os.environ['PATH'] = str(args.root / 'bin') + os.pathsep + os.environ['PATH']
        exe = selected(args.root, c['files'])
        r = {'ambientRunnerObservation': ambient, 'scope': 'QUALIFICATION_ONLY', 'source': binding(), 'root': str(args.root),
             'executable': str(exe), 'resolvedExecutable': str(exe.resolve()), 'symlinkChain': [],
             'archiveSHA256': SHA256, 'archiveSHA512': SHA512, 'url': URL,
             'files': c['files'], 'versionOutput': version(exe),
             'JAVA_HOME': os.environ.get('JAVA_HOME'), 'PATH': os.environ['PATH'],
             'mavenEnvironment': {k: os.environ[k] for k in ('MAVEN_HOME', 'M2_HOME', 'MAVEN_ARGS') if k in os.environ}}
        with args.receipt.open('x') as f: f.write(json.dumps(r, sort_keys=True, indent=2) + '\n')
        with open(os.environ['GITHUB_PATH'], 'a') as f: f.write(str(args.root / 'bin') + '\n')
    r = verify(args.root, args.receipt)
    print(r['versionOutput']); print('Verified Maven distribution', r['archiveSHA256'])


if __name__ == '__main__': main()
