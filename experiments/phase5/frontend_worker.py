"""Bounded, versioned persistent frontend supervisor; no approval authority.

The Python framing process persists; candidate parser CLI processes currently do
not. Timings must never describe this as a warm native parser service.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

AREA=Path(__file__).resolve().parent
sys.path.insert(0,str(AREA))
PROTOCOL="acp-frontend-wire/1"
LIMIT=1048576


class WireFailure(ValueError): pass


def encode(value):
    from run import canonical_bytes
    return canonical_bytes(value)


def request_hash(request): return hashlib.sha256(encode(request)).hexdigest()


class Client:
    def __init__(self,candidate,*,command=None,cwd=None,environment=None):
        self.candidate=candidate
        self.process=subprocess.Popen(command or [sys.executable,str(AREA/"frontend_worker.py"),candidate],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,cwd=cwd,env=environment)
        os.set_blocking(self.process.stdin.fileno(),False)
        os.set_blocking(self.process.stdout.fileno(),False)
        self.seen=set()
        self.pending=b""
        self.closed=False

    def close(self):
        if self.closed:return
        self.closed=True
        try: os.killpg(self.process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        self.process.wait()
        self.process.stdin.close();self.process.stdout.close()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def call(self,request,*,timeout=30,cancelled=None):
        if cancelled is not None and cancelled.is_set():raise WireFailure("CANCELLED")
        if request.get("id") in self.seen:raise WireFailure("DUPLICATE_ID")
        if len(self.seen)>=1024:raise WireFailure("SESSION_LIMIT")
        try:raw=encode(request)+b"\n"
        except ValueError as error:
            raise WireFailure("INPUT_SIZE" if str(error)=="Byte limit exceeded" else "MALFORMED_REQUEST") from None
        if len(raw)>LIMIT:raise WireFailure("INPUT_SIZE")
        self.seen.add(request.get("id"))
        deadline=time.monotonic()+timeout
        cursor=0
        response=self.pending
        self.pending=b""
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.process.stdout,selectors.EVENT_READ)
                selector.register(self.process.stdin,selectors.EVENT_WRITE)
                while b"\n" not in response:
                    if cancelled is not None and cancelled.is_set():raise WireFailure("CANCELLED")
                    if time.monotonic()>deadline:raise WireFailure("TIMEOUT")
                    for key,events in selector.select(.02):
                        if key.fileobj is self.process.stdin:
                            try:cursor+=os.write(self.process.stdin.fileno(),raw[cursor:cursor+65536])
                            except BrokenPipeError:raise WireFailure("CRASH") from None
                            if cursor==len(raw):selector.unregister(self.process.stdin)
                        else:
                            chunk=os.read(self.process.stdout.fileno(),65536)
                            if not chunk:raise WireFailure("CRASH")
                            response+=chunk
                            if len(response)>LIMIT:raise WireFailure("RESPONSE_SIZE")
            line,self.pending=response.split(b"\n",1)
            from canonical_json import loads
            try:result=loads(line)
            except (ValueError,UnicodeError):raise WireFailure("MALFORMED_RESPONSE") from None
            if not isinstance(result,dict) or set(result) != {"protocol","frontend","id","requestDigest","status","payload"} or not isinstance(result["payload"],dict) or result["status"] not in {"SUCCESS","FAILURE"}:raise WireFailure("MALFORMED_RESPONSE")
            if result["protocol"]!=PROTOCOL or result["frontend"]!=request["frontend"]:raise WireFailure("VERSION")
            if result["id"]!=request["id"] or result["requestDigest"]!=request_hash(request):raise WireFailure("STALE_RESPONSE")
            if result["status"]!="SUCCESS":
                if set(result["payload"])!={"code"} or not isinstance(result["payload"]["code"],str):raise WireFailure("MALFORMED_RESPONSE")
                raise WireFailure(result["payload"]["code"])
            return result
        except BaseException:
            self.close()
            raise


def serve(candidate):
    from frontend import TextFrontend
    from compiler_contracts import Source, Document
    from canonical_json import loads
    frontend=TextFrontend(candidate,worker_child=True)
    seen=set()
    for _ in range(1024):
        raw=sys.stdin.buffer.readline(LIMIT+1)
        if not raw:return
        if len(raw)>LIMIT:return
        request={}
        try:
            request=loads(raw)
            if not isinstance(request,dict):
                request={}
                raise WireFailure("MALFORMED_REQUEST")
            if set(request)!={"protocol","frontend","id","source"}:raise WireFailure("MALFORMED_REQUEST")
            if request["protocol"]!=PROTOCOL:raise WireFailure("PROTOCOL_VERSION")
            if request["frontend"]!=frontend.identity:raise WireFailure("FRONTEND_VERSION")
            if not isinstance(request["id"],str) or not request["id"] or len(request["id"])>128:raise WireFailure("REQUEST_ID")
            if request["id"] in seen:raise WireFailure("DUPLICATE_ID")
            seen.add(request["id"])
            parsed=frontend.ingest(Source(Document.of(request["source"])))
            payload={"representation":parsed.representation.read(),"sourceMap":parsed.source_map.read()}
            status="SUCCESS"
        except Exception as error:
            payload={"code":str(error) if isinstance(error,WireFailure) else "FRONTEND_FAILURE"}
            status="FAILURE"
        response={"protocol":PROTOCOL,"frontend":frontend.identity,"id":request.get("id"),"requestDigest":request_hash(request),"status":status,"payload":payload}
        output=encode(response)+b"\n"
        if len(output)>LIMIT:return
        sys.stdout.buffer.write(output);sys.stdout.buffer.flush()


if __name__=="__main__":serve(sys.argv[1])
