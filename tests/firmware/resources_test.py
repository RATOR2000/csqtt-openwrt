import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('resource_report', ROOT / 'scripts/resource-report.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResourceEvidence(unittest.TestCase):
    def run_report(self, changes=None):
        first = dict(schema=1, evidence='resource_sample', scenario='traffic', pid=123, startticks='12345',
                     uptime_cs=10000, rss_kib=1024, hwm_kib=2048, cpu_ticks=100, host_cpu_ticks=1000, mem_available_kib=65536)
        second = {**first, 'uptime_cs': 10500, 'cpu_ticks': 125, 'host_cpu_ticks': 1200, **(changes or {})}
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'samples.jsonl'
            path.write_text(json.dumps(first) + '\n' + json.dumps(second) + '\n', encoding='utf-8')
            return module.report([path])

    def test_valid_samples_do_not_qualify_platform(self):
        result = self.run_report()
        self.assertFalse(result['qualification'])
        self.assertEqual(result['missing_scenarios'], ['auth', 'idle', 'recovery'])
        self.assertEqual(result['scenarios']['traffic']['peak_fraction_all_cpu'], 0.125)

    def test_pid_reuse_rejected(self):
        with self.assertRaisesRegex(ValueError, 'process/scenario changed'):
            self.run_report({'startticks': '12346'})

    def test_coverage_and_counter_reset_rejected(self):
        for change in ({'uptime_cs': 20000}, {'uptime_cs': 10000}, {'host_cpu_ticks': 999}, {'cpu_ticks': 90}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_report(change)

    def test_invalid_memory_and_impossible_cpu_rejected(self):
        for change in ({'rss_kib': 4096}, {'rss_kib': True}, {'cpu_ticks': 9999}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_report(change)


if __name__ == '__main__':
    unittest.main()
