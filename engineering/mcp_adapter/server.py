"""Local stdio MCP transport; SDK owns negotiation, dispatch and cancellation."""
import argparse,sys
from typing import Annotated,Literal
import anyio
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp_types import Tool,ToolAnnotations,ListToolsResult,CallToolResult,TextContent
from engineering.mcp_adapter.service import Service,TOOLS,encode

Identifier=Annotated[str,Field(min_length=1,max_length=180,pattern=r'^[A-Za-z0-9_.:-]+$')]
class Query(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 schemaVersion: Literal['acp-mcp-request/1']='acp-mcp-request/1'
 application: Literal['payment','case-management']
 ids: Annotated[list[Identifier],Field(max_length=8)]=[]
 task: Annotated[str,Field(max_length=256)]=''
 symbol: Identifier|Literal['']=''
 kind: Annotated[str,Field(max_length=64,pattern=r'^[A-Za-z0-9_]*$')]=''
 status: Literal['','PASS','FAIL','BLOCKED','NOT_RUN']=''
 limit: Annotated[int,Field(ge=1,le=50)]=20
 budget: Annotated[int,Field(ge=4096,le=32768)]=16384
 cursor: Annotated[str,Field(max_length=90,pattern=r'^(|[a-f0-9]{64}:[0-9]{1,6})$')]=''

OUTPUT={'type':'object','additionalProperties':False,'properties':{'schema':{'const':'acp-mcp-tool-result/1'},'payload':{'type':['object','null']},'error':{'type':['string','null']}},'required':['schema','payload','error']}
ALLOWED={
 'project.summary':set(),'project.context':{'ids','task'},'spec.query':{'ids','kind'},'spec.validate':set(),
 'compiler.plan':{'ids'},'source.symbol':{'ids','symbol'},'source.references':{'symbol'},'source.impact':{'ids','symbol'},'compiler.verify':{'ids','status'}}
COMMON={'schemaVersion','application','limit','budget','cursor'}

class BoundedInput:
 """Stop the connection before the SDK allocates an unbounded JSON line."""
 def __aiter__(self):return self
 async def __anext__(self):
  raw=await anyio.to_thread.run_sync(lambda:sys.stdin.buffer.readline(65537),abandon_on_cancel=True)
  if not raw:raise StopAsyncIteration
  if len(raw)>65536:raise ValueError('MCP_FRAME_TOO_LARGE')
  return raw.decode('utf-8',errors='strict')

def create(service):
 tools=[Tool(name=n,description='ACP read-only '+n+'; no approval or execution authority.',input_schema=Query.model_json_schema(),output_schema=OUTPUT,annotations=ToolAnnotations(read_only_hint=True,destructive_hint=False,idempotent_hint=True,open_world_hint=False)) for n in TOOLS]
 async def listing(ctx,params):return ListToolsResult(tools=tools)
 async def invoke(ctx,params):
  value=None;error=None
  try:
   if params.name not in TOOLS:raise ValueError('UNSUPPORTED_OPERATION')
   q=Query.model_validate(params.arguments or {})
   if set(q.model_fields_set)-COMMON-ALLOWED[params.name]:raise ValueError('UNSUPPORTED_SELECTOR')
   with anyio.fail_after(30):
    value=await anyio.to_thread.run_sync(lambda:service.call(params.name,q.model_dump()),abandon_on_cancel=True)
  except ValidationError:error='INVALID_ARGUMENTS'
  except TimeoutError:error='INSPECTION_TIMEOUT'
  except (OSError,KeyError,TypeError,ValueError) as exc:
   # Never disclose rejected values, filesystem paths or internal exception logs.
   code=str(exc);error=code if code.isupper() and code.replace('_','').isalnum() and len(code)<80 else 'INPUT_INTEGRITY_FAILURE'
  result={'schema':'acp-mcp-tool-result/1','payload':value,'error':error}
  return CallToolResult(content=[TextContent(type='text',text=encode(result).decode())],structured_content=result,is_error=error is not None)
 return Server('ACP read-only MCP',version='0.1.0',instructions='Host-selected approved applications only. Results are observations, never semantic approval or release acceptance.',get_tool_input_schema=lambda n:Query.model_json_schema() if n in TOOLS else None,on_list_tools=listing,on_call_tool=invoke)

async def serve(config):
 service=Service(config);server=create(service)
 async with stdio_server(stdin=BoundedInput()) as (incoming,outgoing):
  await server.run(incoming,outgoing,server.create_initialization_options())

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-config',required=True);a=p.parse_args()
 try:anyio.run(serve,a.host_config)
 except Exception:
  print('ACP_MCP_HOST_OR_TRANSPORT_REJECTED',file=sys.stderr);raise SystemExit(2)
if __name__=='__main__':main()
