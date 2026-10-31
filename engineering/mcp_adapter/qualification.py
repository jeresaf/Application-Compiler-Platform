"""Bounded real-client MCP qualification; never executes application workloads."""
import argparse,importlib.metadata,json,os,platform,subprocess,unittest
from pathlib import Path
from engineering.mcp_adapter.service import encode,sha

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 config=Path(a.host_config).absolute();output=Path(a.output).absolute();output.mkdir(mode=0o700,exist_ok=False)
 os.environ.update(ACP_MCP_HOST_CONFIG=str(config),ACP_MCP_RESULTS=str(output/'measurements.json'))
 suite=unittest.defaultTestLoader.discover('verification/mcp_adapter');count=suite.countTestCases()
 if count!=10:raise ValueError('MCP_TEST_INVENTORY')
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 record={'schema':'acp-mcp-qualification/1','scope':'READ_ONLY_QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'python':platform.python_version(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'hostConfigSHA256':sha(config.read_bytes()),'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'releaseDisposition':'PHASE6_RELEASE_CLOSURE_BLOCKED'}
 (output/'qualification.json').write_bytes(encode(record))
 if not result.wasSuccessful() or result.skipped or result.testsRun!=count:raise SystemExit(1)
if __name__=='__main__':main()
