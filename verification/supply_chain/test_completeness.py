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

    def test_edges_require_exact_packaged_endpoints(self):
        from engineering.supply_chain.completeness import packaged_maven_edges, verify_projected_edges

        def node(name, children=(), *, classifier=''):
            return {'groupId': 'org.example', 'artifactId': name, 'version': '1',
                    'type': 'jar', 'children': list(children), 'classifier': classifier}

        a, b = 'a' * 64, 'b' * 64
        packaged = [
            {'identity': {'name': 'org.example:' + name, 'version': '1', 'sha256': pin},
             'sha256': pin, 'origins': [f'maven:org/example/{name}/1/{name}-1.jar']}
            for name, pin in (('a', a), ('b', b))
        ]
        bom = {'components': [
            {'bom-ref': name, 'name': 'org.example:' + name, 'version': '1',
             'hashes': [{'content': pin}]}
            for name, pin in (('a', a), ('b', b))
        ]}
        graph = node('application', [node('a', [node('b'), node('b', classifier='tests')])])
        edges, unmapped = packaged_maven_edges(graph, packaged, bom)
        self.assertEqual(edges, [{'ref': 'a', 'dependsOn': ['b']}])
        self.assertEqual(unmapped, 2)
        with self.assertRaisesRegex(ValueError, 'PACKAGED_EDGE_RECONCILIATION'):
            verify_projected_edges(bom | {'dependencies': []}, edges, Draft7Validator({}))
        with self.assertRaisesRegex(ValueError, 'PACKAGED_ENDPOINT_DIGEST'):
            packaged_maven_edges(graph, [packaged[0] | {'sha256': b}, packaged[1]], bom)
