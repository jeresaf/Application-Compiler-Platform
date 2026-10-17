"""Laboratory inspection; never admits evidence to release closure."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def inspect_submission(raw):
    from engineering.evidence_admission.scoped.manifest import manifest,digest
    value=manifest(raw)
    return {'status':'STRUCTURE_VALID_UNTRUSTED','manifestDigest':digest(raw),
            'purpose':value['purpose'],'phase6':'IN_PROGRESS','phase7':'NOT_STARTED',
            'recommendation':'PHASE6_CLOSURE_BLOCKED','releaseClosure':'PHASE6_RELEASE_CLOSURE_BLOCKED'}


def release_bridge(result):
    # Even a genuinely reverified laboratory result is not an operational capability.
    from engineering.evidence_admission.scoped.verify import LabQualification
    if type(result) is LabQualification:result.reverify()
    raise ValueError('LABORATORY_RESULT_CANNOT_AUTHORIZE_RELEASE')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    with args.manifest.open('rb') as stream:raw=stream.read(1024*1024+1)
    print(json.dumps(inspect_submission(raw),sort_keys=True))
    raise SystemExit(2)
