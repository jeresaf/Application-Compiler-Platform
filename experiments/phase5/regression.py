"""Run all existing experiments; native Phase 5C tests run once via run5c.py."""
import unittest
from run import AREA

def without_native_gate(suite):
    result=unittest.TestSuite()
    for item in suite:
        if isinstance(item,unittest.TestSuite):result.addTest(without_native_gate(item))
        elif item.__class__.__module__!='test_phase5c':result.addTest(item)
    return result
if __name__=='__main__':
    tests=unittest.defaultTestLoader.discover(str(AREA),pattern='test_*.py')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(without_native_gate(tests)).wasSuccessful())
