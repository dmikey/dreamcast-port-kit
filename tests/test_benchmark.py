from pathlib import Path
import importlib.util,unittest
spec=importlib.util.spec_from_file_location('benchmark',Path(__file__).resolve().parents[1]/'benchmark.py');benchmark=importlib.util.module_from_spec(spec);spec.loader.exec_module(benchmark)
class BenchmarkTests(unittest.TestCase):
    def test_weighted_intervals_skip_partial_first_window(self):
        def event(time,frames,average):return {'timeMs':time,'kind':'RENDER','message':f'[RENDER] frames={frames} submit_avg_us={average} submit_max_us=9000'}
        report={'events':[event(1000,3,9999),event(6000,300,100),event(11000,150,400)]}
        result=benchmark.summarize(report)
        self.assertEqual(result['renderWindows'],2);self.assertEqual(result['submittedFramesPerSecond'],45);self.assertEqual(result['submitAverageUs'],200)
    def test_empty_or_truncated_reports_do_not_invent_fps(self):
        result=benchmark.summarize({'eventsDropped':10,'events':[]});self.assertIsNone(result['submittedFramesPerSecond']);self.assertEqual(result['eventsDropped'],10)

    def test_worker_window_duration_is_independent_of_delayed_page_delivery(self):
        report={'events':[{'kind':'RENDER','timeMs':1000,'message':'[RENDER] frames=10 submit_avg_us=100 submit_max_us=100 window_us=5000000'},{'kind':'RENDER','timeMs':1100,'message':'[RENDER] frames=300 submit_avg_us=100 submit_max_us=100 window_us=5000000'}]}
        self.assertEqual(benchmark.summarize(report)['submittedFramesPerSecond'],60)
