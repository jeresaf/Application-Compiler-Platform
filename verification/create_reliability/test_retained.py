"""Synthetic integrity tests; real CREATE proof comes only from disposable JVM/PG runs."""
import json,tempfile,unittest
from pathlib import Path
from engineering.create_reliability.diagnostic import verify_retained
from engineering.source_intelligence.model import sha


class Retained(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for kind in ('classes','test-classes'):
            p=self.root/'outputs/backend/target'/kind/'example.class';p.parent.mkdir(parents=True);p.write_bytes(kind.encode())
        consumed={'backendMainClasses':{'example.class':sha(b'classes')},'backendTestClasses':{'example.class':sha(b'test-classes')}}
        p=self.root/'build/consumed-build.json';p.parent.mkdir();p.write_text(json.dumps(consumed))
        self.value={'files':{'build/consumed-build.json':sha(p.read_bytes())},'generator':{'generator':'acp-h1-job-preview-generator/1+sha256:f982b13e43e0efd070ea1b0773da5aedcdbf2486363c6e902f27c36ba00bcb02'},'sealed05':'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb','scope':'QUALIFICATION_ONLY','cleanup':'VERIFIED'}
        self.save()
    def save(self):
        self.record=self.root/'result.json';self.record.write_text(json.dumps(self.value));self.pin=sha(self.record.read_bytes())
    def check(self):return verify_retained(self.root,self.pin)
    def test_exact_retained_classes(self):self.assertEqual(len(self.check()['backendMainClasses']),1)
    def test_result_change(self):
        self.record.write_bytes(self.record.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'RESULT_CHANGED'):self.check()
    def test_consumed_map_change(self):
        (self.root/'build/consumed-build.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'CONSUMED_BUILD_CHANGED'):self.check()
    def test_production_class_change(self):
        (self.root/'outputs/backend/target/classes/example.class').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError,'CLASS_SUBSTITUTION'):self.check()
    def test_adapter_class_change(self):
        (self.root/'outputs/backend/target/test-classes/example.class').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError,'CLASS_SUBSTITUTION'):self.check()
    def test_extra_production_class(self):
        (self.root/'outputs/backend/target/classes/extra.class').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError,'CLASS_SUBSTITUTION'):self.check()
    def test_wrong_generator(self):
        self.value['generator']['generator']='other';self.save()
        with self.assertRaisesRegex(ValueError,'GENERATOR'):self.check()
    def test_operational_scope_rejected(self):
        self.value['scope']='RELEASE_ACCEPTED';self.save()
        with self.assertRaisesRegex(ValueError,'SCOPE'):self.check()


class Classpath(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.jar=self.root/'org/example/1.0/example-1.0.jar';self.jar.parent.mkdir(parents=True);self.jar.write_bytes(b'locked jar')
        self.reference={'schema':'acp-maven-inputs/1','artifacts':{'org/example/1.0/example-1.0.jar':{'sha256':sha(b'locked jar'),'size':10}}}
    def check(self,path=None):
        from engineering.create_reliability.diagnostic import classpath_inventory
        return classpath_inventory(str(path or self.jar),self.root,self.reference)
    def test_locked_runtime_input(self):self.assertEqual(len(self.check()),1)
    def test_substituted_jar(self):
        self.jar.write_bytes(b'other jar!')
        with self.assertRaisesRegex(ValueError,'SUBSTITUTION'):self.check()
    def test_outside_classpath(self):
        with self.assertRaisesRegex(ValueError,'ESCAPE'):self.check(self.root.parent/'outside.jar')
    def test_unregistered_jar(self):
        with self.assertRaisesRegex(ValueError,'UNREGISTERED'):self.check(self.root/'unknown.jar')
