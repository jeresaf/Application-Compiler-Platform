"""Retain the new native gate tests as reviewable raw evidence."""
import io,json,time,unittest
from run import AREA
import test_phase5c

def run():
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_phase5c);stream=io.StringIO();start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    target=AREA/'results/phase5c';target.mkdir(exist_ok=True)
    (target/'native-tests.log').write_text(stream.getvalue())
    (target/'native-tests.json').write_text(json.dumps({'status':'PASS' if result.wasSuccessful() else 'FAIL','testsRun':result.testsRun,'elapsedSeconds':time.perf_counter()-start,'failures':len(result.failures),'errors':len(result.errors),'scope':'True native workers, actual compiler Failure and independent full-pipeline concurrency; max two native workers.'},indent=2)+'\n')
    print(stream.getvalue());return not result.wasSuccessful()
if __name__=='__main__':raise SystemExit(run())
