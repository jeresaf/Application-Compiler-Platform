"""Historical upgrade harness: read original 0.1 inline provenance unchanged.

The current production reader supports 0.2/0.3. The sealed 0.1 generator
emitted the same inline origin structure under version 0.1.0; this test-only
adapter preserves that evidence and all existing upgrade assertions.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_target_profile_upgrade as upgrade
from target_provenance import read_provenance as current_reader


def read_historical_provenance(path):
    value = json.loads(Path(path).read_text())
    if value.get('version') == '0.1.0':
        for mapping in value['artifacts']:
            origins = mapping['origins']
            if (not origins or len({o['id'] for o in origins}) != len(origins)
                    or any(type(o['revision']) is not int or o['revision'] < 1 for o in origins)):
                raise ValueError('PROVENANCE_ORIGINS')
        return value
    return current_reader(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--new-projects', type=Path, required=True)
    args = parser.parse_args()
    upgrade.read_provenance = read_historical_provenance
    upgrade.run(args.output.resolve(), args.new_projects.resolve())
