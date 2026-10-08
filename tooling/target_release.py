"""Immutable semantic generator identity binds one exact released worker bundle."""
import json
from pathlib import Path

def verify_release(profile,bundle,registry=None):
    if registry is None:
        registry=json.loads((Path(__file__).resolve().parents[1]/'targets/spring-vue-postgres/release-contract.json').read_text())
    if registry.get('contractVersion')!='1.0.0':raise ValueError('RELEASE_CONTRACT_VERSION')
    release=registry.get('releases',{}).get(profile['profile'])
    if not release or release['generator']!=profile['generator']:raise ValueError('GENERATOR_VERSION_UNRELEASED')
    if release['bundleDigest']!=bundle.removeprefix('sha256:'):raise ValueError('GENERATOR_VERSION_REUSE')
    return release

def verify_preserved_releases(previous,current):
    for identity,entry in previous.get('releases',{}).items():
        if current.get('releases',{}).get(identity)!=entry:raise ValueError('RELEASE_IDENTITY_REWRITE')
    return True
