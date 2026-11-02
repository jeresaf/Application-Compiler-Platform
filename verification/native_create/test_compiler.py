"""Existing kernel integration and fail-closed version/authority boundaries."""
import copy,unittest
from dataclasses import replace
from engineering.native_create import compiler as c
from engineering.native_create.reference import proposal
from compiler_contracts import Success,Failure,Stage
from compiler_core import compile_pipeline as old_compile
import compiler_core

class NativeCompiler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source,cls.ctx=c.fixture_context(proposal())
        cls.result=c.compile_pipeline(cls.source,cls.ctx)
    def test_all_original_stages_execute_with_create_and_obligations(self):
        self.assertIsInstance(self.result.result,Success)
        self.assertEqual(self.result.audit.status,'COMPLETE')
        self.assertEqual(len(self.result.stages),8)
        plan=self.result.result.output
        ids={o.id for a in plan.artifacts for o in a.mappings}
        self.assertTrue({'CREATE-CASE','PERM-CREATE-CASE','FORM-CREATE-CASE'}<=ids)
        categories={o.category for o in plan.obligations if any(s.id=='CREATE-CASE' for s in o.origins)}
        self.assertTrue({'authorization','audit','tests','reliability'}<=categories)
        self.assertTrue(all(o.status=='OUTSTANDING' for o in plan.obligations))
    def test_existing_kernel_globals_and_default_negotiation_unchanged(self):
        self.assertNotIn('CreateOperation',compiler_core.APPLICATION_KINDS)
        self.assertEqual(compiler_core.COMPILER,'acp-reference-compiler/0.1.0')
        self.assertIsInstance(old_compile(self.source,self.ctx).result,Failure)
        private=c.kernel()
        self.assertIs(private['_project'].__code__,compiler_core._project.__code__)
        self.assertIs(private['validate_plan'].__code__,compiler_core.validate_plan.__code__)
        self.assertIsNot(private['compile_pipeline'].__globals__,compiler_core.compile_pipeline.__globals__)
    def test_unknown_feature_and_missing_capability_fail_closed(self):
        bad=replace(self.ctx,request=replace(self.ctx.request,features=('unknown',)))
        with self.assertRaises(ValueError):c.compile_pipeline(self.source,bad)
        bad=replace(self.ctx,request=replace(self.ctx.request,required_capabilities=()))
        self.assertIsInstance(c.compile_pipeline(self.source,bad).result,Failure)
    def test_revoked_preview_allowlist_is_not_authority_bypass(self):
        self.ctx.approval.revoked=True
        try:self.assertIsInstance(c.compile_pipeline(self.source,self.ctx).result,Failure)
        finally:self.ctx.approval.revoked=False

if __name__=='__main__':unittest.main()
