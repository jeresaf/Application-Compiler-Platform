import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from engineering.hardening.target import harden_pom, PLUGIN_VERSIONS


class DependencyPolicy(unittest.TestCase):
    def test_plugin_realms_have_exact_compatible_override(self):
        root = ET.fromstring(harden_pom('<project><build><plugins></plugins></build></project>'))
        plugins = root.findall('./build/pluginManagement/plugins/plugin')
        self.assertEqual(len(plugins), len(PLUGIN_VERSIONS))
        for plugin in plugins:
            name = plugin.findtext('artifactId')
            self.assertEqual(plugin.findtext('version'), PLUGIN_VERSIONS[name])
            dependency = plugin.find('./dependencies/dependency')
            self.assertEqual([dependency.findtext(k) for k in ('groupId', 'artifactId', 'version')],
                             ['commons-io', 'commons-io', '2.22.0'])

    def test_missing_parent_marker_rejected(self):
        with self.assertRaisesRegex(ValueError, 'H1_PARENT_POM_DRIFT'):
            harden_pom('<project/>')

    def test_spring_boot_packager_realm_is_explicitly_overridden(self):
        root = ET.fromstring(harden_pom('<project><build><plugins></plugins></build></project>'))
        plugins = root.findall('./build/pluginManagement/plugins/plugin')
        boot = [p for p in plugins if p.findtext('artifactId') == 'spring-boot-maven-plugin']
        self.assertEqual(len(boot), 1)
        self.assertEqual(boot[0].findtext('groupId'), 'org.springframework.boot')
        self.assertEqual(boot[0].findtext('./dependencies/dependency/version'), '2.22.0')

    def test_duplicate_parent_marker_rejected(self):
        with self.assertRaisesRegex(ValueError, 'H1_PARENT_POM_DRIFT'):
            harden_pom('<build><plugins><build><plugins>')

    def test_existing_plugin_management_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'H1_PARENT_POM_DRIFT'):
            harden_pom('<build><plugins></plugins><pluginManagement/></build>'.replace(
                '<pluginManagement/>', '<pluginManagement></pluginManagement>'))

    def test_exact_locked_artifact_available(self):
        lock = json.loads(Path('engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes())
        self.assertEqual(lock['artifacts']['commons-io/commons-io/2.22.0/commons-io-2.22.0.jar']['sha256'],
                         '2b9a7b1f726fb86216dbd2c8321eabe0221dbd5b1be81c18e1cb53811b104758')

    def test_successor_input_lock_preserves_parent_bytes(self):
        import hashlib
        lock = json.loads(Path('engineering/hardening/plugin-inputs.lock.json').read_bytes())
        parent = Path(lock['parentInputLock']).read_bytes()
        self.assertEqual(hashlib.sha256(parent).hexdigest(), lock['parentInputLockSHA256'])
        self.assertEqual(json.loads(parent)['artifacts'][lock['replacement']['path']],
                         {k: lock['replacement'][k] for k in ('sha256', 'size')})
        self.assertEqual(lock['scope'], 'QUALIFICATION_ONLY')


if __name__ == '__main__':
    unittest.main()
