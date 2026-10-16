"""Qualify the fixed reviewed V3 export, never the CI branch's changed source."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

COMMIT = '584ca9edce76886ff351fd93edef9d3343a5a61c'
CANDIDATE = '325265709357b355a1644e8411c13e701d5e0786e5f5fd6ecfa43ba2ce9dfd0c'
MANIFEST = '5033d915410e8f2eaf4d53f4a041795c931bb57c36abdf105ba88f57298176e6'
PATCH = '9706ba0c436f57560b0e8ace897cee7f1f258c2d40870e8bf1c9c2da70b791c8'
MANIFEST_PATH = 'engineering/ci/phase6-qualification-manifest.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_patch(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != PATCH:
        raise ValueError('MISSING_OR_WRONG_WAVE3_PATCH')


def restore_checkout_bytes(name, data, baseline):
    # Git stores LF; the reviewed export pinned eleven historical CRLF fixtures.
    # Restore only a baseline fixture whose exact reviewed hash matches conversion.
    expected = baseline.get(name)
    if expected and sha(data) != expected and name.startswith('test-corpus/'):
        converted = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        if sha(converted) == expected:
            return converted
        if name == 'test-corpus/semantic/cases.json':
            # This historical fixture has one LF amid CRLF lines.
            mixed = converted.replace(b'\"value\": \"99.0.0\"\r\n', b'\"value\": \"99.0.0\"\n')
            if sha(mixed) == expected:
                return mixed
    return data


def export_candidate(repository, destination, patch):
    verify_patch(patch)
    repository, destination = Path(repository).resolve(), Path(destination).resolve()
    if destination.is_relative_to(repository):
        raise ValueError('EXPORT_MUST_BE_OUTSIDE_CHECKOUT')
    archive = subprocess.run(['git', 'archive', '--format=tar', COMMIT], cwd=repository,
                             capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        members = tree.getmembers()
        for member in members:
            name = Path(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isdir() or member.isfile()):
                raise ValueError('UNSAFE_GIT_EXPORT')
        manifest = tree.extractfile(MANIFEST_PATH).read()
        if sha(manifest) != MANIFEST:
            raise ValueError('WRONG_REVIEWED_MANIFEST')
        baseline = json.loads(manifest)['baselineFileHashes']
        files = {m.name: restore_checkout_bytes(m.name, tree.extractfile(m).read(), baseline)
                 for m in members if m.isfile()}
    digest = sha(json.dumps({n: sha(b) for n, b in files.items()},
                            sort_keys=True, separators=(',', ':')).encode())
    if digest != CANDIDATE or len(files) != 905:
        raise ValueError('WRONG_REVIEWED_CANDIDATE')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in files.items():
        output = destination / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    return destination


def verify_negative_bindings(source, patch):
    """Exercise corrected exact-V3 rejection checks without altering the export."""
    source = Path(source)
    spec = importlib.util.spec_from_file_location(
        'reviewed_v3_qualification', source / 'engineering/ci/phase6_qualification.py')
    qualification = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qualification)
    manifest = source / MANIFEST_PATH
    identities = dict(expected_manifest=MANIFEST, expected_candidate=CANDIDATE)
    qualification.validate_candidate(source, patch, manifest, **identities)
    checked = []

    def reject(label, root, supplied_patch, supplied_manifest, expected_error, **overrides):
        try:
            qualification.validate_candidate(root, supplied_patch, supplied_manifest,
                                             **{**identities, **overrides})
        except ValueError as error:
            if str(error) != expected_error:
                raise AssertionError('UNEXPECTED_BINDING_REJECTION:' + label) from error
            checked.append(label)
        else:
            raise AssertionError('BINDING_ACCEPTED_INVALID_INPUT:' + label)

    reject('wrong-baseline', source, patch, manifest,
           'BASELINE_PATCH_OR_MANIFEST_MISMATCH', baseline='wrong')
    reject('changed-candidate-digest', source, patch, manifest,
           'CANDIDATE_IDENTITY_MISMATCH', expected_candidate='0' * 64)
    with tempfile.TemporaryDirectory(prefix='acp-v3-binding-negatives-') as temporary:
        temporary = Path(temporary)
        wrong = temporary / 'wrong.patch'
        wrong.write_bytes(b'not the verified patch')
        reject('changed-patch', source, wrong, manifest,
               'BASELINE_PATCH_OR_MANIFEST_MISMATCH')
        wrong_manifest = temporary / 'wrong-manifest.json'
        wrong_manifest.write_bytes(manifest.read_bytes() + b' ')
        reject('changed-manifest', source, patch, wrong_manifest,
               'BASELINE_PATCH_OR_MANIFEST_MISMATCH')
        damaged = temporary / 'damaged-source'
        shutil.copytree(source, damaged)
        (damaged / '.gitattributes').unlink()
        reject('missing-source-file', damaged, patch, damaged / MANIFEST_PATH,
               'CANDIDATE_IDENTITY_MISMATCH')
    return checked


def prerequisites(source):
    if platform.python_implementation() != 'CPython' or platform.python_version() != '3.14.7':
        raise ValueError('MISSING_PINNED_CPYTHON_3_14_7')
    versions = {}
    for line in (Path(source) / 'tooling/requirements.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        name, expected = line.split('==')
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as error:
            raise ValueError('MISSING_PREPROVISIONED_DEPENDENCY:' + name) from error
        if actual != expected:
            raise ValueError('WRONG_PREPROVISIONED_DEPENDENCY:' + name)
        versions[name] = actual
    subprocess.run([sys.executable, '-B', '-m', 'pip', 'check'], check=True)
    return versions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository', 'patch', 'export', 'scratch', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    source = export_candidate(args.repository, args.export, args.patch)
    versions = prerequisites(source)
    negative_bindings = verify_negative_bindings(source, args.patch)
    command = [sys.executable, '-B', str(source / 'engineering/ci/phase6_qualification.py'),
               '--offline', '--source', str(source), '--patch', str(Path(args.patch).resolve()),
               '--manifest', str(source / MANIFEST_PATH), '--manifest-sha256', MANIFEST,
               '--candidate-sha256', CANDIDATE, '--scratch', args.scratch,
               '--output', args.output, '--python', sys.executable]
    print(json.dumps({'qualificationCommit': COMMIT, 'candidateSHA256': CANDIDATE,
                      'manifestSHA256': MANIFEST, 'patchSHA256': PATCH,
                      'python': platform.python_version(), 'packages': versions,
                      'negativeBindingsPassed': negative_bindings,
                      'argv': command}), flush=True)
    return subprocess.run(command, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
