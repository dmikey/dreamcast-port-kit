from pathlib import Path
import importlib.util,os,unittest
path=Path(__file__).resolve().parents[1]/'validation/sh4_subset.py'
spec=importlib.util.spec_from_file_location('subset_oracle',path);oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
@unittest.skipUnless(os.environ.get('DC_PORT_TEST_TOOLCHAIN'),'Set DC_PORT_TEST_TOOLCHAIN')
class DifferentialTests(unittest.TestCase):
 def test_translated_integer_control_flow_and_ordered_writes_match_oracle(self):
  report=oracle.validate(os.environ['DC_PORT_TEST_TOOLCHAIN'],programs=4,cases=32,seed=0x4dc)
  self.assertEqual(report['comparisons'],128);self.assertEqual(report['mismatches'],0)
 def test_deliberately_corrupted_candidate_is_rejected(self):
  def corrupt(code):return code.replace('return; /* rts */','cpu->r[0]^=1;return; /* rts */')
  with self.assertRaises(oracle.ValidationMismatch):oracle.validate(os.environ['DC_PORT_TEST_TOOLCHAIN'],programs=1,cases=2,seed=1,mutate=corrupt)
