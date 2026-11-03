import tempfile
import unittest
from pathlib import Path
from engineering.hardening.assessment import parse_realms, verify_realms, ARTIFACT


def observed(version='2.22.0'):
    return '\n'.join('[DEBUG] Populating class realm plugin>org.apache.maven.plugins:'+p+
                     '\n[DEBUG]   Included: commons-io:commons-io:jar:'+version
                     for p in ('maven-resources-plugin:3.5.0', 'maven-compiler-plugin:3.15.0'))


class Observation(unittest.TestCase):
    def test_two_actual_realm_identities_required(self):
        self.assertEqual(len(parse_realms(observed())), 2)

    def test_vulnerable_realm_rejected(self):
        with self.assertRaises(ValueError):
            parse_realms(observed('2.11.0'))

    def test_pom_declaration_is_not_execution_evidence(self):
        with self.assertRaises(ValueError):
            parse_realms('<dependency>commons-io:2.22.0</dependency>')

    def test_missing_compiler_realm_rejected(self):
        with self.assertRaises(ValueError):
            parse_realms(observed().split('[DEBUG] Populating class realm', 2)[1])

    def test_unexpected_vulnerable_realm_rejected(self):
        with self.assertRaises(ValueError):
            parse_realms(observed()+'\n[DEBUG] Populating class realm plugin>other:1\n'
                         '[DEBUG] Included: commons-io:commons-io:jar:2.11.0')

    def test_duplicate_realm_rejected(self):
        with self.assertRaises(ValueError):
            parse_realms(observed()+'\n'+observed())

    def test_substituted_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/ARTIFACT
            path.parent.mkdir(parents=True)
            path.write_bytes(b'substituted')
            with self.assertRaisesRegex(ValueError, 'H1_DEPENDENCY_SUBSTITUTION'):
                verify_realms(observed(), folder)

    def test_missing_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                verify_realms(observed(), folder)
