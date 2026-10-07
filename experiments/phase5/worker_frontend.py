"""Phase 4 frontend port backed by the actual bounded frontend worker protocol."""
from frontend import TextFrontend
from frontend_worker import PROTOCOL
from compiler_contracts import Document, Ingested


class WorkerFrontend(TextFrontend):
    def __init__(self,candidate,client):
        super().__init__(candidate)
        self.client=client
        self.sequence=0

    def ingest(self,source):
        self.sequence+=1
        response=self.client.call({"protocol":PROTOCOL,"frontend":self.identity,
            "id":f"ingest-{self.sequence}","source":source.document.read()})
        payload=response["payload"]
        if set(payload)!={"representation","sourceMap"}:raise ValueError("RESPONSE")
        return Ingested(Document.of(payload["representation"]),Document.of(payload["sourceMap"]),self.identity)
