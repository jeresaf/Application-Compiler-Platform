import unittest
from pathlib import Path
from dataclasses import replace
from test_manifest import Fixture,canonicalize,parse_canonical,D


class WitnessTests(unittest.TestCase):
    def test_exact_git_source_consumption_and_modes(self):
        f=Fixture();self.addCleanup(f.close);f.run()
        (f.source/'Witness.java').chmod(0o755)
        with self.assertRaises(ValueError):f.run()

    def test_duplicate_argv_is_ordered_not_a_set(self):
        f=Fixture();self.addCleanup(f.close)
        scope=parse_canonical(f.context.scope);scope['expectedInputs']['argv']=['synthetic','x','x']
        f.payload['observedInputs']=scope['expectedInputs']
        f.context=replace(f.context,scope=canonicalize(scope),observations=(canonicalize(f.payload),))
        self.assertEqual(f.run().status,'QUALIFICATION_ONLY')

    def test_missing_or_extra_case_is_not_an_independent_pass(self):
        f=Fixture();self.addCleanup(f.close);f.payload['cases'].pop()
        with self.assertRaises(ValueError):f.run()

    def test_valid_signature_does_not_override_registered_execution(self):
        f=Fixture();self.addCleanup(f.close);f.payload['observedInputs']['executableDigest']=D('replacement')
        with self.assertRaises(ValueError):f.run()

    def test_resource_signal_and_cleanup_observations_fail_closed(self):
        for key,value in [('termination',{'kind':'SIGNAL','signalNumber':9,'coreDumped':False}),('termination',{'kind':'NORMAL_EXIT','exitCode':1}),('resourceLimitEvents',['MEMORY_LIMIT']),('monotonicDurationNanoseconds',30_000_000_001)]:
            with self.subTest(key=key,value=value):
                f=Fixture();self.addCleanup(f.close);f.payload[key]=value
                f.context=replace(f.context,observations=(canonicalize(f.payload),))
                with self.assertRaises(ValueError):f.run()

    def test_unsafe_artifacts_and_xml_are_rejected_after_authenticated_capture(self):
        from test_adversarial import rebind
        for raw in (b'<!DOCTYPE x [<!ENTITY x "boom">]><testsuite/>',b'<testsuite tests="1" skipped="1"><testcase classname="lab.Witness" name="externalWitness"/></testsuite>',b'<testsuite tests="0"/>',b'<testsuite><testcase classname="lab.Witness" name="externalWitness"><rerunFailure/></testcase></testsuite>'):
            with self.subTest(raw=raw):
                f=Fixture(human=True);self.addCleanup(f.close)
                (f.artifacts/'payment.xml').write_bytes(raw);rebind(f)
                with self.assertRaises(ValueError):f.run()

    def test_artifact_hardlink_fifo_and_read_race_rejected(self):
        import os
        from unittest.mock import patch
        from engineering.evidence_admission.scoped.verify import capture
        for mode in ('hardlink','fifo','race'):
            with self.subTest(mode=mode):
                f=Fixture();self.addCleanup(f.close);p=f.artifacts/'payment.xml'
                if mode=='hardlink':os.link(p,f.root/'external-alias')
                if mode=='fifo':p.unlink();os.mkfifo(p)
                if mode=='race':
                    original=os.read;changed=False
                    def read(fd,n):
                        nonlocal changed
                        data=original(fd,n)
                        if not changed:
                            p.write_bytes(p.read_bytes()+b'changed');changed=True
                        return data
                    with patch('engineering.evidence_admission.scoped.verify.os.read',read):
                        with self.assertRaises(ValueError):capture(f.artifacts,f.m['artifacts'])
                else:
                    with self.assertRaises(ValueError):capture(f.artifacts,f.m['artifacts'])

    def test_context_rejects_unknown_profiles_and_checkpoint_forks(self):
        for field,value in [('policy_ref',canonicalize({'schema':'unknown','payloadDigest':D('x')})),('registration_ref',canonicalize({'schema':'unknown','payloadDigest':D('x')})),('expected_checkpoint',canonicalize({'sequence':3,'digest':D('old')})),('checkpoint_expires_at','2026-10-17T11:59:00Z')]:
            with self.subTest(field=field):
                f=Fixture();self.addCleanup(f.close)
                with self.assertRaises(ValueError):replace(f.context,**{field:value})

    def test_sealed_release_lab_result_still_cannot_clear_release(self):
        from test_adversarial import rebind
        from tooling.audit.scoped_admission import release_bridge
        f=Fixture(human=True);self.addCleanup(f.close)
        release={'kind':'SEALED_RELEASE','profile':'acp-spring-vue-postgres/0.5.0','generator':'acp-spring-vue-generator/0.5.0','releaseContractDigest':'sha256:2f2a10ea29c4f6083352c8b49e5d2d715b0797bdd36b6cad3db762a03d7e4605','bundleSeal':f.m['release']['parentBundleSeal']}
        f.m['release']=release;f.m['purpose']='SEALED_RELEASE_EVALUATION';f.payload['release']=release
        scope=parse_canonical(f.context.scope);scope['release']=release
        grant=parse_canonical(f.context.review_grants[0]);grant['release']=release
        f.review['release']=release
        f.context=replace(f.context,release=canonicalize(release),scope=canonicalize(scope),review_grants=(canonicalize(grant),))
        rebind(f)
        self.assertEqual(f.run().status,'QUALIFICATION_ONLY')
        with self.assertRaises(ValueError):release_bridge(f.run())

    def test_directory_replacement_and_namespace_aba_rejected(self):
        import os
        from unittest.mock import patch
        from engineering.evidence_admission.scoped.verify import capture
        for restore in (False,True):
            f=Fixture();self.addCleanup(f.close)
            original=os.read;changed=False
            def read(fd,n):
                nonlocal changed
                raw=original(fd,n)
                if not changed:
                    changed=True
                    old=f.artifacts.with_name('old-artifacts')
                    f.artifacts.rename(old);f.artifacts.mkdir()
                    if restore:
                        f.artifacts.rmdir();old.rename(f.artifacts)
                return raw
            with self.subTest(restore=restore),patch('engineering.evidence_admission.scoped.verify.os.read',read):
                with self.assertRaises((ValueError,OSError)):capture(f.artifacts,f.m['artifacts'])

    def test_source_replacement_and_inventory_addition_rejected(self):
        from unittest.mock import patch
        import os
        for mode in ('replace','extra','symlink'):
            f=Fixture();self.addCleanup(f.close)
            original=os.read;changed=False
            def read(fd,n):
                nonlocal changed
                raw=original(fd,n)
                if not changed:
                    changed=True;p=f.source/'Witness.java'
                    if mode=='extra':(f.source/'unexpected').write_bytes(b'x')
                    elif mode=='symlink':p.unlink();p.symlink_to(f.root/'missing')
                    else:
                        data=p.read_bytes();p.unlink();p.write_bytes(data)
                return raw
            with self.subTest(mode=mode),patch('engineering.evidence_admission.scoped.verify.os.read',read):
                with self.assertRaises((ValueError,OSError)):f.run()

    def test_forged_git_commit_and_blob_reads_rejected(self):
        from unittest.mock import patch
        from engineering.evidence_admission.scoped import witnesses
        for kind in ('commit','blob'):
            f=Fixture();self.addCleanup(f.close);original=witnesses.git_read
            def read(root,*args):
                raw=original(root,*args)
                return raw+b'forged' if args[:2]==('cat-file',kind) else raw
            with self.subTest(kind=kind),patch.object(witnesses,'git_read',read):
                with self.assertRaises(ValueError):f.run()

    def test_corrupt_tree_object_at_expected_oid_rejected(self):
        import subprocess,zlib
        f=Fixture();self.addCleanup(f.close)
        oid=subprocess.check_output(['/usr/bin/git','-C',str(f.source),'rev-parse','HEAD^{tree}'],text=True).strip()
        obj=f.source/'.git'/'objects'/oid[:2]/oid[2:]
        raw=zlib.decompress(obj.read_bytes())
        obj.chmod(0o600);obj.write_bytes(zlib.compress(raw.replace(b'Witness.java',b'Altered.java')))
        with self.assertRaises(ValueError):f.run()

    def test_nested_directory_replacement_rejected(self):
        from unittest.mock import patch
        import os
        from engineering.evidence_admission.scoped.verify import capture
        f=Fixture();self.addCleanup(f.close)
        directory=f.root/'nested-artifacts';directory.mkdir();sub=directory/'reports';sub.mkdir()
        raw=b'bounded';(sub/'result').write_bytes(raw)
        entry={'path':'reports/result','size':len(raw)}
        from engineering.evidence_admission.scoped.manifest import sha
        entry['sha256']=sha(raw)
        original=os.read;changed=False
        def read(fd,n):
            nonlocal changed
            data=original(fd,n)
            if not changed:
                changed=True;sub.rename(directory/'detached');sub.mkdir();(sub/'result').write_bytes(raw)
            return data
        with patch('engineering.evidence_admission.scoped.verify.os.read',read):
            with self.assertRaises((ValueError,OSError)):capture(directory,[entry])

    def test_prior_file_mutation_during_later_capture_rejected(self):
        from unittest.mock import patch
        import os
        from engineering.evidence_admission.scoped.verify import capture
        from engineering.evidence_admission.scoped.manifest import sha
        f=Fixture();self.addCleanup(f.close);root=f.root/'multi';root.mkdir()
        for name in ('one','two'):(root/name).write_bytes(b'expected')
        entries=[{'path':name,'size':8,'sha256':sha(b'expected')} for name in ('one','two')]
        original=os.read;first=None;changed=False
        def read(fd,n):
            nonlocal first,changed
            data=original(fd,n);inode=os.fstat(fd).st_ino
            if first is None:first=inode
            elif inode!=first and not changed:
                changed=True
                prior=next(p for p in root.iterdir() if p.stat().st_ino==first)
                prior.write_bytes(b'modified')
            return data
        with patch('engineering.evidence_admission.scoped.verify.os.read',read):
            with self.assertRaises(ValueError):capture(root,entries)

    def test_git_directory_replaced_by_symlink_during_object_read_rejected(self):
        from unittest.mock import patch
        from engineering.evidence_admission.scoped import witnesses
        f=Fixture();self.addCleanup(f.close);original=witnesses.git_read;changed=False
        def read(root,*args):
            nonlocal changed
            raw=original(root,*args)
            if args[:2]==('cat-file','commit') and not changed:
                changed=True;git=f.source/'.git';saved=f.root/'detached-git'
                git.rename(saved);git.symlink_to(saved,target_is_directory=True)
            return raw
        with patch.object(witnesses,'git_read',read):
            with self.assertRaises(ValueError):f.run()

    def test_git_transport_and_lazy_fetch_are_disabled(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from engineering.evidence_admission.scoped import witnesses
        with patch.object(witnesses.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'object')) as run:
            self.assertEqual(witnesses.git_read(Path('/synthetic'),'cat-file','blob','0'*40),b'object')
        env=run.call_args.kwargs['env']
        self.assertEqual(env['GIT_ALLOW_PROTOCOL'],'')
        self.assertEqual(env['GIT_NO_LAZY_FETCH'],'1')
        self.assertEqual(env['GIT_NO_REPLACE_OBJECTS'],'1')
        self.assertNotIn('GIT_CONFIG_COUNT',env)
        self.assertEqual(run.call_args.args[0][0],'/usr/bin/git')
