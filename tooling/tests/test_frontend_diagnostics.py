"""Port diagnostic metadata is bounded, immutable and safe through real Failure."""
from dataclasses import replace
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compiler_contracts import Stage,Failure,Resources,Document
from compiler_core import execute
from compiler_ports import SourceDiagnostic,FrontendDiagnosticsFailure
from compiler_fixtures import small_model
from compiler_reference import fixture_context

class DiagnosticBoundaryTests(unittest.TestCase):
    def result(self,diagnostics,resources=None):
        source,ctx=fixture_context(small_model())
        class Port:
            identity=ctx.frontend.identity
            def ingest(self,source):raise FrontendDiagnosticsFailure(diagnostics)
        ctx=replace(ctx,frontend=Port())
        if resources:ctx=replace(ctx,request=replace(ctx.request,resources=resources))
        return execute(Stage.INGEST,source,ctx)
    def test_unsafe_codes_paths_subjects_and_confidence_fail_closed(self):
        for d in (SourceDiagnostic('secret-token',None,None),SourceDiagnostic('ACP-FRONTEND-SYNTAX',None,'/tmp/secret#L1C1',confidence='TOKEN'),SourceDiagnostic('ACP-FRONTEND-SYNTAX',('secret / token',1),None),SourceDiagnostic('ACP-FRONTEND-SYNTAX',None,'source.acp#L1C1',confidence='UNRECOVERABLE')):
            result=self.result((d,));self.assertIsInstance(result,Failure);self.assertEqual('ACP-COMPILER-PORT',result.diagnostics[0].code);self.assertFalse(hasattr(result,'output'));self.assertNotIn('secret',repr(result))
    def test_order_related_locations_and_output_bound(self):
        a=SourceDiagnostic('ACP-REF',('ENT-A',1),'a.acp#L2C7',(('ENT-B',1),),('b.acp#L1C8',),'TOKEN')
        b=SourceDiagnostic('ACP-FRONTEND-SYNTAX',None,None)
        first=self.result((a,b));second=self.result((b,a))
        self.assertEqual(first.diagnostics,second.diagnostics);self.assertEqual(('b.acp#L1C8',),first.diagnostics[1].related_locations)
        result=self.result((a,),Resources(output_bytes=32));self.assertIsInstance(result,Failure);self.assertEqual('ACP-COMPILER-PORT',result.diagnostics[0].code)
if __name__=='__main__':unittest.main()
