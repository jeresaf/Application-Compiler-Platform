import copy
import unittest
from jsonschema import Draft7Validator, ValidationError

from engineering.supply_chain.completeness import native_tools, read_archive, validate_bom


class CompletenessTests(unittest.TestCase):
    def test_corrupt_archive_rejected_before_parsing(self):
        with self.assertRaisesRegex(ValueError, 'RECONCILIATION_ARCHIVE'):
            read_archive(b'not the pinned evidence')

    def test_unknown_executable_fails_closed(self):
        toolchains = {'executables': {'mvn': '/maven/bin/mvn'}, 'versions': {'maven': '3.10.0'},
                      'inventories': {'maven': {'root': '/maven', 'files': {}}}}
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_TOOL_BYTES'):
            native_tools(toolchains)

    def test_schema_and_content_constraints_are_independent(self):
        schema = Draft7Validator({'type': 'object', 'required': ['components']})
        bom = {'specVersion': '1.6', 'components': [
            {'bom-ref': 'one', 'name': 'pkg', 'version': '1', 'hashes': [{'content': 'a'*64}]}],
            'compositions': [{'aggregate': 'incomplete', 'assemblies': ['one']}]}
        expected = [('pkg', '1', 'a'*64)]
        validate_bom(bom, expected, schema)
        with self.assertRaises(ValidationError):
            validate_bom({}, expected, schema)
        for field, value in [('name', 'substituted'), ('hashes', [{'content': 'b'*64}])]:
            bad = copy.deepcopy(bom)
            bad['components'][0][field] = value
            with self.assertRaisesRegex(ValueError, 'BOM_COMPONENT_RECONCILIATION'):
                validate_bom(bad, expected, schema)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_BOM_REFERENCE'):
            validate_bom(bom | {'components': bom['components'] * 2}, expected, schema)
        with self.assertRaisesRegex(ValueError, 'BOM_COMPLETENESS'):
            validate_bom(bom | {'compositions': [{'aggregate': 'complete', 'assemblies': ['one']}]},
                         expected, schema)
