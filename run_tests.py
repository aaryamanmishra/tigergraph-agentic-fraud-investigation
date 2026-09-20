"""
Comprehensive Test Suite Runner.
Executes all unit and regression tests across policy, approvals, exposure, schema, integrity, and HHG-001.
"""

import sys
import unittest
import time


def run_all_tests():
    print("======================================================================")
    print("      TIGERGRAPH AGENTIC FRAUD INVESTIGATION — TEST SUITE            ")
    print("======================================================================")
    start_time = time.time()

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    duration = time.time() - start_time

    print("\n======================================================================")
    print(f"Total Tests Run:  {result.testsRun}")
    print(f"Passed:           {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed:           {len(result.failures)}")
    print(f"Errors:           {len(result.errors)}")
    print(f"Execution Time:   {duration:.2f} seconds")
    print("======================================================================")

    if result.wasSuccessful():
        print("ALL TESTS PASSED SUCCESSFULLY.")
        return 0
    else:
        print("SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
