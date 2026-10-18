"""Fail-closed resolution tests; real offline build evidence is produced separately."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.dependency_resolution.inputs import *


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='acp-dep-unit-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_exact_tree_and_substituted_or_extra_file(self):
        p=self.root/'dependency.jar';p.write_bytes(b'original');expected=inventory(self.root);verify_tree(self.root,expected)
        p.write_bytes(b'replaced')
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_SUBSTITUTION'):verify_tree(self.root,expected)
        p.write_bytes(b'original');(self.root/'extra.jar').write_bytes(b'new')
        with self.assertRaises(ValueError):verify_tree(self.root,expected)

    def test_read_access_time_does_not_masquerade_as_content_mutation(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import os
        p=self.root/'artifact';p.write_bytes(b'verified bytes');real=os.fstat
        def with_changed_atime(fd):
            s=real(fd)
            return SimpleNamespace(**{name:getattr(s,name) for name in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')},st_atime=s.st_atime+1)
        with patch('os.fstat',side_effect=with_changed_atime):self.assertEqual(file_hash(p),hashlib.sha256(b'verified bytes').hexdigest())

    def test_missing_and_symlink_inputs(self):
        p=self.root/'x';p.write_bytes(b'content');expected=inventory(self.root);p.unlink()
        with self.assertRaises(ValueError):verify_tree(self.root,expected)
        p.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError,'SYMLINK'):inventory(self.root)

    def test_immutable_versions_reject_mutable_resolution(self):
        for v in ('LATEST','RELEASE','1.0-SNAPSHOT','[1,2)','^1.2.3','~2','*','${version}','https://registry/1'):
            with self.subTest(version=v),self.assertRaises(ValueError):exact_version(v)
        for v in ('1.0','3.1.0-RC1','4.2.0.Final'):self.assertEqual(exact_version(v),v)

    def test_lock_hash_and_scope_cannot_be_recomputed_by_consumer(self):
        p=self.root/'lock';good={'schema':'acp-dependency-qualification/1','scope':'UNSEALED_CANDIDATE_QUALIFICATION_ONLY'};p.write_bytes(encode(good));pin=file_hash(p);self.assertEqual(load_lock(p,pin),good)
        p.write_bytes(encode(dict(good,extra='tampered')))
        with self.assertRaisesRegex(ValueError,'LOCK_SUBSTITUTION'):load_lock(p,pin)
        p.write_bytes(encode(dict(good,scope='SEALED_RELEASE')))
        with self.assertRaisesRegex(ValueError,'LOCK_SCOPE'):load_lock(p,file_hash(p))

    def npm(self):return {'lockfileVersion':3,'packages':{'':{'version':'1.0.0'},'node_modules/vue':{'version':'3.5.43','resolved':'https://registry.npmjs.org/vue/-/vue-3.5.43.tgz','integrity':'sha512-'+base64.b64encode(b'x'*64).decode()}}}

    def test_npm_complete_exact_resolution(self):
        value=npm_lock(encode(self.npm()));self.assertEqual(value['node_modules/vue']['version'],'3.5.43')

    def test_npm_git_http_file_range_and_missing_hash_rejected(self):
        for key,value in [('resolved','git+https://x'),('resolved','http://x'),('resolved','file:local'),('version','^3.5.43'),('integrity',''),('integrity','sha512-forged'),('link',True)]:
            n=self.npm();n['packages']['node_modules/vue'][key]=value
            with self.subTest(field=key,value=value),self.assertRaises(ValueError):npm_lock(encode(n))

    def maven(self):
        base=self.root/'org/example/library/1.2.3';base.mkdir(parents=True)
        (base/'library-1.2.3.jar').write_bytes(b'library');(base/'library-1.2.3.pom').write_bytes(b'pom')
        plugin=self.root/'org/apache/maven/plugins/compile/3.0';plugin.mkdir(parents=True)
        (plugin/'compile-3.0.jar').write_bytes(b'plugin with its own closure');(plugin/'compile-3.0.pom').write_bytes(b'plugin pom')
        graph={'groupId':'acp.generated','artifactId':'application','version':'0.1.0','children':[{'groupId':'org.example','artifactId':'library','version':'1.2.3','type':'jar','scope':'runtime'}]}
        return graph,inventory(self.root)

    def test_maven_inventory_contains_plugins_and_poms_not_just_runtime(self):
        graph,files=self.maven();result=maven_closure(graph,self.root,files)
        self.assertEqual(len(result['resolvedGraph']),1);self.assertEqual(len(result['allRuntimeAndBuildArtifacts']),4)
        self.assertIn('org/apache/maven/plugins/compile/3.0/compile-3.0.jar',result['allRuntimeAndBuildArtifacts'])

    def test_maven_missing_parent_or_runtime_and_mutable_nodes(self):
        graph,files=self.maven();missing=dict(files);del missing['org/example/library/1.2.3/library-1.2.3.pom']
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_MAVEN'):maven_closure(graph,self.root,missing)
        graph['children'][0]['version']='1.2.3-SNAPSHOT'
        with self.assertRaisesRegex(ValueError,'MUTABLE_DEPENDENCY_VERSION'):maven_closure(graph,self.root,files)

    def test_plugin_substitution_fails_same_as_runtime_substitution(self):
        graph,files=self.maven();p=self.root/'org/apache/maven/plugins/compile/3.0/compile-3.0.jar';p.write_bytes(b'substitute')
        with self.assertRaisesRegex(ValueError,'SUBSTITUTION'):verify_tree(self.root,files)

    def wheel(self):
        p=self.root/'fixture-1.0-py3-none-any.whl'
        with zipfile.ZipFile(p,'w') as z:z.writestr('fixture-1.0.dist-info/METADATA','Name: fixture\nVersion: 1.0\n');z.writestr('fixture/__init__.py','content')
        req=self.root/'requirements';req.write_text('fixture==1.0 --hash=sha256:'+file_hash(p)+'\n');return p,req

    def test_compiler_wheel_exact_version_hash_and_missing_dependency(self):
        p,req=self.wheel();self.assertEqual(wheel_inputs(self.root,req,False)['fixture']['version'],'1.0');p.write_bytes(p.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'COMPILER_WHEEL_SUBSTITUTION'):wheel_inputs(self.root,req,False)
        p.unlink()
        with self.assertRaisesRegex(ValueError,'MISSING_COMPILER_WHEEL'):wheel_inputs(self.root,req,False)

    def test_unpinned_compiler_resolution_rejected(self):
        req=self.root/'requirements';req.write_text('fixture>=1.0\n')
        with self.assertRaisesRegex(ValueError,'UNPINNED_COMPILER'):wheel_inputs(self.root,req,False)

    def test_independent_packages_require_both_domains_and_exact_bytes(self):
        good={'payment':{'packageSHA256':'p'},'case-management':{'packageSHA256':'c'}}
        self.assertEqual(compare_packages(good,copy.deepcopy(good))['status'],'QUALIFICATION_ONLY')
        changed=copy.deepcopy(good);changed['payment']['packageSHA256']='different'
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_CLEAN_BUILD_MISMATCH'):compare_packages(good,changed)
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_APPLICATION_COVERAGE'):compare_packages(good,{'payment':good['payment']})

    def test_pipeline_is_offline_after_freeze_and_does_not_skip_tests(self):
        source=(ROOT/'engineering/dependency_resolution/qualify.py').read_text()
        self.assertIn("['-o'] if offline else []",source);self.assertIn("'--offline'",source)
        self.assertIn('LOCK', (ROOT/'engineering/dependency_resolution/inputs.py').read_text())
        self.assertNotIn('-DskipTests',source);self.assertNotIn('-Dmaven.test.skip',source)
        self.assertIn("for label in ('one','two')",source);self.assertIn("'clean','test-compile',JAR,BOOT",source)
        self.assertNotIn('psql',source);self.assertNotIn('spring-boot:run',source)

    def test_compiler_pin_versions_match_existing_compiler_requirements(self):
        old={l.split('==')[0]:l.split('==')[1] for l in (ROOT/'tooling/requirements.txt').read_text().splitlines() if l and not l.startswith('#')}
        new={l.split('==')[0]:l.split('==')[1].split()[0] for l in (ROOT/'engineering/dependency_resolution/compiler-requirements.txt').read_text().splitlines() if l and not l.startswith('#')}
        self.assertEqual(old,new)

    def test_actual_npm_versions_and_extracted_bytes_are_verified(self):
        folder=self.root/'node_modules/vue';folder.mkdir(parents=True);p=folder/'package.json';p.write_text('{"name":"vue","version":"3.5.43"}')
        locked=npm_lock(encode(self.npm()));before=installed_npm(self.root,locked)
        p.write_text('{"name":"vue","version":"3.5.42"}')
        with self.assertRaisesRegex(ValueError,'INSTALLED_NPM_VERSION_OR_IDENTITY'):installed_npm(self.root,locked)
        p.write_text('{"name":"vue","version":"3.5.43"}');(folder/'extra.js').write_text('substituted code')
        self.assertNotEqual(before,installed_npm(self.root,locked))

    def test_npm_executable_links_cannot_escape_locked_installation(self):
        folder=self.root/'node_modules/vue';folder.mkdir(parents=True);(folder/'package.json').write_text('{"name":"vue","version":"3.5.43"}')
        (folder/'unsafe').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError,'NPM_BIN_ESCAPE'):installed_npm(self.root,npm_lock(encode(self.npm())))

    def test_maven_seed_rejects_substitution_before_any_plugin_execution(self):
        seed=self.root/'seed';seed.mkdir();p=seed/'org/example/library/1.0/library-1.0.jar';p.parent.mkdir(parents=True);p.write_bytes(b'exact artifact')
        reference={'schema':'acp-maven-inputs/1','scope':'UNSEALED_CANDIDATE_QUALIFICATION_ONLY','artifacts':inventory(seed)}
        seed_maven(seed,self.root/'copy',reference)
        p.write_bytes(b'replaced')
        with self.assertRaisesRegex(ValueError,'PINNED_MAVEN_SUBSTITUTION'):seed_maven(seed,self.root/'rejected',reference)

    def test_fresh_resolution_cannot_bless_changed_graph_or_plugin_selection(self):
        graph,files=self.maven();reference={'artifacts':files,'graphs':{'payment':graph},'plugins':{'payment':['fixed-plugin-3.0.jar']}}
        verify_maven_resolution('payment',graph,['fixed-plugin-3.0.jar'],files,reference)
        changed=copy.deepcopy(graph);changed['children'][0]['version']='1.2.4'
        with self.assertRaisesRegex(ValueError,'PINNED_MAVEN_GRAPH_DRIFT'):verify_maven_resolution('payment',changed,['fixed-plugin-3.0.jar'],files,reference)
        with self.assertRaisesRegex(ValueError,'PINNED_PLUGIN_RESOLUTION_DRIFT'):verify_maven_resolution('payment',graph,['mutable-plugin.jar'],files,reference)

    def test_plugin_embedded_jars_have_exact_container_origin(self):
        repo=self.root/'m2';repo.mkdir();p=repo/'plugin.jar';payload=b'exact embedded binary'
        with zipfile.ZipFile(p,'w') as z:z.writestr('META-INF/tool.jar',payload)
        files=inventory(repo);embedded=embedded_jars(repo,files);row=embedded['plugin.jar!/META-INF/tool.jar'];self.assertEqual(row['containerSHA256'],file_hash(p));self.assertEqual(row['sha256'],digest(payload))
        built=self.root/'application.jar'
        with zipfile.ZipFile(built,'w') as z:z.writestr('BOOT-INF/lib/tool-1.0.jar',payload)
        self.assertEqual(packaged_dependencies(built,files,embedded)['BOOT-INF/lib/tool-1.0.jar']['lockedOrigins'],['embedded:plugin.jar!/META-INF/tool.jar'])

    def test_unknown_packaged_jars_and_changed_plugin_container_rejected(self):
        repo=self.root/'m2';repo.mkdir();p=repo/'plugin.jar'
        with zipfile.ZipFile(p,'w') as z:z.writestr('META-INF/tool.jar',b'exact')
        files=inventory(repo);embedded=embedded_jars(repo,files)
        built=self.root/'application.jar'
        with zipfile.ZipFile(built,'w') as z:z.writestr('BOOT-INF/lib/tool-1.0.jar',b'substitute')
        with self.assertRaisesRegex(ValueError,'UNLOCKED_PACKAGED_DEPENDENCY'):packaged_dependencies(built,files,embedded)
        p.write_bytes(b'changed plugin')
        with self.assertRaisesRegex(ValueError,'EMBEDDED_CONTAINER_SUBSTITUTION'):embedded_jars(repo,files)

    def test_sealed_predicates_and_candidate_sources_unchanged(self):
        import subprocess
        self.assertEqual(subprocess.check_output(['git','diff','1db17ec','--','tooling','contracts','targets','test-corpus','engineering/generator_candidates'],cwd=ROOT),b'')


if __name__=='__main__':unittest.main()
