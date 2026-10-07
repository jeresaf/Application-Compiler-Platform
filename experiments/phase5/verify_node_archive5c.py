"""Verify official Node archive checksum before extraction or execution."""
import hashlib
from run import AREA
folder=AREA/'.cache/phase5c-toolchains'
archive=folder/'node-v22.20.0-linux-x64.tar.xz'
sums=(folder/'node-v22.20.0-SHASUMS256.txt').read_text()
assert f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}' in sums
print('Node previous-toolchain archive checksum PASS')
