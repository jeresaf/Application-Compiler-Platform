"""Actual frontend-worker protocol, authority separation and lifecycle failures."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from threading import Event,Timer
import time
import unittest

AREA=Path(__file__).resolve().parent
sys.path.insert(0,str(AREA))
from frontend_worker import Client,PROTOCOL,WireFailure,LIMIT
from frontend import TextFrontend
from worker_frontend import WorkerFrontend
from test_phase5b import source_context
from run import ROOT
from compiler_contracts import Stage,Success
from compiler_core import execute
from canonical_fixtures import synthetic_approved


class WorkerTests(unittest.TestCase):
    def request(self,candidate,id="one"):
        model=synthetic_approved(json.loads((ROOT/"test-corpus/phase1/payment.json").read_text()))
        source,ctx=source_context(candidate,model)
        return {"protocol":PROTOCOL,"frontend":ctx.frontend.identity,"id":id,"source":source.document.read()},source,ctx

    def test_real_candidates_persistent_restart_retry_and_actual_ingest(self):
        for candidate in ("antlr","langium","xtext"):
            request,source,ctx=self.request(candidate)
            with Client(candidate) as client:
                one=client.call(request)
                two=client.call({**request,"id":"two"})
                self.assertEqual(one["payload"],two["payload"])
                with self.assertRaisesRegex(WireFailure,"DUPLICATE_ID"):client.call(request)
                port=WorkerFrontend(candidate,client)
                parsed=execute(Stage.INGEST,source,replace(ctx,frontend=port))
                self.assertIsInstance(parsed,Success,parsed)
                ast=execute(Stage.ELABORATE,parsed.output,replace(ctx,frontend=port))
                self.assertIsInstance(ast,Success,ast)
            with Client(candidate) as restarted:
                self.assertEqual(one["payload"],restarted.call(request)["payload"])
            with Client(candidate,command=[sys.executable,"-c","raise SystemExit(2)"]) as crashed:
                with self.assertRaisesRegex(WireFailure,"CRASH"):crashed.call(request)
            with Client(candidate) as retried:
                self.assertEqual(one["payload"],retried.call(request)["payload"])
            self.assertIsNotNone(ctx.approval)  # Host authority outlives every disposable worker.

    def test_protocol_frontend_versions_malformed_request_and_size(self):
        request,_,_=self.request("langium")
        for field,value,code in (("protocol","unknown/9","PROTOCOL_VERSION"),("frontend","acp-experiment-langium/0","VERSION")):
            with Client("langium") as client,self.assertRaisesRegex(WireFailure,code):client.call({**request,field:value})
        with Client("langium") as client,self.assertRaisesRegex(WireFailure,"MALFORMED_REQUEST"):
            client.call({k:v for k,v in request.items() if k!="source"})
        with Client("langium") as client,self.assertRaisesRegex(WireFailure,"INPUT_SIZE"):
            client.call({**request,"source":"x"*LIMIT})

    def test_faults_stale_oversize_timeout_and_cancellation(self):
        request,_,_=self.request("langium")
        fixtures={"MALFORMED_RESPONSE":"print('???')", "RESPONSE_SIZE":"print('x'*1048577)",
                  "TIMEOUT":"import time; time.sleep(5)",
                  "STALE_RESPONSE":"import json,sys; r=json.loads(sys.stdin.readline()); print(json.dumps({'protocol':r['protocol'],'frontend':r['frontend'],'id':'old','requestDigest':'old','status':'SUCCESS','payload':{}}))"}
        for expected,script in fixtures.items():
            with Client("langium",command=[sys.executable,"-c",script]) as client,self.assertRaisesRegex(WireFailure,expected):client.call(request,timeout=.2)
        for delay in (0,.1):
            event=Event()
            timer=None
            if delay:timer=Timer(delay,event.set);timer.start()
            else:event.set()
            with Client("langium",command=[sys.executable,"-c","import time; time.sleep(5)"]) as client,self.assertRaisesRegex(WireFailure,"CANCELLED"):
                client.call(request,cancelled=event)
            if timer:timer.join()


if __name__=="__main__":unittest.main()
