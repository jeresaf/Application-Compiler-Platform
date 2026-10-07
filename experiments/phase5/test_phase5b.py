"""Phase 5B: actual compiler entry, module visibility and stable-label operations."""
from dataclasses import replace
import copy
import json
from pathlib import Path
import sys
import unittest

AREA = Path(__file__).resolve().parent
sys.path.insert(0, str(AREA))
from run import ROOT
from generate import encode
from frontend import TextFrontend
from modules import resolve, ModuleError
from compiler_contracts import Source, Document, Stage, Success, Failure, fingerprint
from compiler_core import execute, compile_pipeline
from compiler_reference import fixture_context
from canonical_fixtures import synthetic_approved


def source_context(candidate, model, documents=None):
    frontend = TextFrontend(candidate)
    _, context = fixture_context(model)
    source = Source(Document.of({"version":"acp-text/1", "frontend":frontend.identity,
        "documents":documents or [{"path":"domain.acp", "text":encode(model)}]}))
    request = replace(context.request, frontend=frontend.identity, source_digest=fingerprint(source,"source"))
    return source, replace(context, request=request, frontend=frontend)


class TextBoundaryTests(unittest.TestCase):
    def test_real_frontends_enter_ingest_then_elaborate_and_entire_pipeline(self):
        for candidate in ("antlr","langium","xtext"):
            for domain in ("payment","case-management"):
                with self.subTest(candidate=candidate,domain=domain):
                    model=synthetic_approved(json.loads((ROOT/f"test-corpus/phase1/{domain}.json").read_text()))
                    source, context=source_context(candidate,model)
                    parsed=execute(Stage.INGEST,source,context)
                    self.assertIsInstance(parsed,Success,parsed)
                    ast=execute(Stage.ELABORATE,parsed.output,context)
                    self.assertIsInstance(ast,Success,ast)
                    self.assertEqual(model,ast.output.model.read())
                    self.assertEqual(set(n["id"] for n in model["nodes"]),set(ast.output.source_map.read()))
                    self.assertNotIn("$type",ast.output.model.data.decode())
                    result=compile_pipeline(source,context)
                    self.assertIsInstance(result.result,Success,result.result)

    def test_invalid_source_version_and_recovery_never_succeed(self):
        model=synthetic_approved(json.loads((ROOT/"test-corpus/phase1/payment.json").read_text()))
        for candidate in ("antlr","langium","xtext"):
            source,context=source_context(candidate,model)
            for version in ("acp-text/0","acp-text/2"):
                raw=source.document.read();raw["version"]=version
                bad=replace(source,document=Document.of(raw))
                ctx=replace(context,request=replace(context.request,source_digest=fingerprint(bad,"source")))
                self.assertIsInstance(execute(Stage.INGEST,bad,ctx),Failure)
            raw=source.document.read();raw["documents"][0]["text"]="application {"
            bad=replace(source,document=Document.of(raw))
            ctx=replace(context,request=replace(context.request,source_digest=fingerprint(bad,"source")))
            self.assertIsInstance(execute(Stage.INGEST,bad,ctx),Failure)

    def test_malformed_unsupported_and_framework_frontend_responses(self):
        from compiler_contracts import Ingested,SemanticAST
        from unittest.mock import patch
        model=synthetic_approved(json.loads((ROOT/"test-corpus/phase1/payment.json").read_text()))
        source,ctx=source_context("langium",model)
        # Exact executable response version, not just the host manifest string.
        for output in ({"candidate":"Langium 0.0.0","model":model,"errors":[],"spans":[]},[],None):
            with patch("frontend.invoke",return_value={"status":"PASS","output":output}):
                self.assertIsInstance(execute(Stage.INGEST,source,ctx),Failure)
        class BadPort:
            identity=ctx.frontend.identity
            def ingest(self,source):return Ingested(Document.of(model),Document.of({}),self.identity)
            def elaborate(self,parsed):return self.output
        port=BadPort();context=replace(ctx,frontend=port)
        parsed=execute(Stage.INGEST,source,context);self.assertIsInstance(parsed,Success)
        for output in (object(),{"$type":"FrameworkAST"},SemanticAST(Document.of(model),Document.of({}),version="unsupported"),SemanticAST(Document.of(model),Document.of({"UNKNOWN":"domain.acp#L1C1"})),SemanticAST(Document.of(model),Document.of({model["nodes"][0]["id"]:"/tmp/private.acp#L1C1"}))):
            port.output=output
            self.assertIsInstance(execute(Stage.ELABORATE,parsed.output,context),Failure)

    def test_safe_integer_range_and_unsafe_rejection(self):
        model=synthetic_approved(json.loads((ROOT/"test-corpus/phase1/payment.json").read_text()))
        model["nodes"][0]["revision"]=9007199254740991
        for candidate in ("antlr","langium","xtext"):
            frontend=TextFrontend(candidate)
            raw={"version":"acp-text/1","frontend":frontend.identity,"documents":[{"path":"domain.acp","text":encode(model)}]}
            self.assertEqual(model,frontend.ingest(Source(Document.of(raw))).representation.read())
            raw["documents"][0]["text"]=raw["documents"][0]["text"].replace('@ 9007199254740991','@ 9007199254740992')
            with self.assertRaises(ValueError):frontend.ingest(Source(Document.of(raw)))


class LabelEditSafetyTests(unittest.TestCase):
    def test_unicode_nested_names_and_id_tokens(self):
        from refactor import rename_label
        text='Entity "ENT-A" @ 1 {"data":{"name":"é"},"name":"é"};\nEntity "ENT-B" @ 1 {"peer":ref "a::é" @ 1};\n'
        updated=rename_label([{"path":"a.acp","text":text}],"a","ENT-A","é","ENT-A")[0]["text"]
        self.assertIn('"data":{"name":"é"}',updated)
        self.assertIn('Entity "ENT-A" @ 1',updated)
        self.assertIn('ref "a::ENT-A" @ 1',updated)
        self.assertIn('"name":"ENT-A"',updated)


class ModulePolicyTests(unittest.TestCase):
    def project(self):
        header={"applicationId":"APP-MODULE", "modelVersion":"0.2.0", "snapshotId":"SNAP-MODULE", "approvals":[],"issues":[]}
        a={"id":"ENT-A","revision":1,"kind":"Entity","name":"Original label","data":{}}
        b={"id":"ENT-B","revision":1,"kind":"Entity","name":"B","data":{"owner":{"id":"a::Original label","revision":1}}}
        return [("a.acp",{"module":"a","imports":[],"exports":["ENT-A"],"model":{**header,"nodes":[a]}}),
                ("b.acp",{"module":"b","imports":["a"],"exports":[],"model":{**header,"nodes":[b]}})]

    def test_same_module_policy_real_parsers_and_cross_file_labels(self):
        from refactor import rename_label
        for candidate in ("antlr","langium","xtext"):
            project=self.project()
            documents=[]
            for path,output in project:
                text=f'module {json.dumps(output["module"])};\n'+''.join(f'import {json.dumps(x)};\n' for x in output["imports"])+encode(output["model"])
                if output["exports"]:text=text.replace('\nEntity ', '\nexport Entity ')
                documents.append({"path":path,"text":text})
            frontend=TextFrontend(candidate)
            source=Source(Document.of({"version":"acp-text/1","frontend":frontend.identity,"documents":documents}))
            before=frontend.elaborate(frontend.ingest(source))
            self.assertEqual({"id":"ENT-A","revision":1}, before.model.read()["nodes"][1]["data"]["owner"])
            updated=rename_label(documents,"a","ENT-A","Original label","New label")
            raw=source.document.read();raw["documents"]=updated
            after=frontend.elaborate(frontend.ingest(Source(Document.of(raw))))
            self.assertEqual(["ENT-A","ENT-B"],[n["id"] for n in after.model.read()["nodes"]])
            self.assertEqual(before.model.read()["nodes"][1],after.model.read()["nodes"][1])
            self.assertEqual("New label",after.model.read()["nodes"][0]["name"])
            self.assertTrue(all("#L" in span for span in after.source_map.read().values()))

    def test_missing_duplicate_ambiguous_cycle_visibility_deleted_renamed(self):
        cases={"MISSING_MODULE":lambda p:p[1][1]["imports"].append("missing"),
               "DUPLICATE_IMPORT":lambda p:p[1][1]["imports"].append("a"),
               "CYCLIC_IMPORT":lambda p:p[0][1]["imports"].append("b"),
               "VISIBILITY":lambda p:p[0][1].update(exports=[]),
               "AMBIGUOUS_MODULE":lambda p:p.append(copy.deepcopy(p[0]))}
        for code,edit in cases.items():
            project=self.project();edit(project)
            with self.subTest(code=code),self.assertRaisesRegex(ModuleError,code):resolve(project)
        project=self.project();project.pop(0)
        with self.assertRaisesRegex(ModuleError,"MISSING_MODULE"):resolve(project)
        project=self.project();project[0][1]["module"]="renamed"
        with self.assertRaisesRegex(ModuleError,"MISSING_MODULE"):resolve(project)
        project[1][1]["imports"]=["renamed"]
        project[1][1]["model"]["nodes"][0]["data"]["owner"]["id"]="renamed::Original label"
        self.assertEqual("ENT-A",resolve(project)[0]["nodes"][1]["data"]["owner"]["id"])

    @staticmethod
    def ambiguous_import(project):
        extra=copy.deepcopy(project[0][1]);extra['module']='c';extra['exports']=['ENT-C'];extra['model']['nodes'][0]['id']='ENT-C'
        project.append(('c.acp',extra))
        project[1][1]['imports'].append('c')
        project[1][1]['model']['nodes'][0]['data']['owner']['id']='Original label'

    def test_negative_module_policy_through_every_real_parser(self):
        cases={"MISSING_MODULE":lambda p:p[1][1]["imports"].append("missing"),
               "DUPLICATE_IMPORT":lambda p:p[1][1]["imports"].append("a"),
               "CYCLIC_IMPORT":lambda p:p[0][1]["imports"].append("b"),
               "VISIBILITY":lambda p:p[0][1].update(exports=[]),
               "AMBIGUOUS_MODULE":lambda p:p.append(("duplicate.acp",copy.deepcopy(p[0][1]))),
               "AMBIGUOUS_IMPORT":self.ambiguous_import}
        for candidate in ("antlr","langium","xtext"):
            for code,edit in cases.items():
                project=self.project();edit(project);documents=[]
                for path,o in project:
                    text='module '+json.dumps(o["module"])+';\n'+''.join('import '+json.dumps(x)+';\n' for x in o["imports"])+encode(o["model"])
                    if o["exports"]:text=text.replace('\nEntity ','\nexport Entity ')
                    documents.append({"path":path,"text":text})
                frontend=TextFrontend(candidate)
                source=Source(Document.of({"version":"acp-text/1","frontend":frontend.identity,"documents":documents}))
                with self.subTest(candidate=candidate,code=code),self.assertRaisesRegex(ModuleError,code):frontend.ingest(source)

    def test_legacy_fixture_explicitly_rejected_and_label_identity_is_canonical(self):
        from refactor import rename_label
        from canonical_ir import normalize_candidate
        model=synthetic_approved(json.loads((ROOT/"test-corpus/phase1/payment.json").read_text()))
        target=model["nodes"][0]
        for candidate in ("antlr","langium","xtext"):
            frontend=TextFrontend(candidate)
            documents=[{"path":"domain.acp","text":'module "domain";\n'+encode(model)}]
            source=Source(Document.of({"version":"acp-text/1","frontend":frontend.identity,"documents":documents}))
            before=frontend.ingest(source).representation.read()
            updated=rename_label(documents,"domain",target["id"],target["name"],"Renamed display label")
            raw=source.document.read();raw["documents"]=updated
            after=frontend.ingest(Source(Document.of(raw))).representation.read()
            a=normalize_candidate(before);b=normalize_candidate(after)
            self.assertEqual([(n["id"],n["revision"]) for n in a["content"]["nodes"]],[(n["id"],n["revision"]) for n in b["content"]["nodes"]])
            raw["documents"][0]["text"]=(AREA/"corpora/legacy-v0.acp").read_text()
            with self.assertRaises(ValueError):frontend.ingest(Source(Document.of(raw)))


if __name__ == "__main__":unittest.main()
