#!/usr/bin/env python3
"""Validate owner-collected resource samples. Never qualifies a platform alone."""
import argparse
import json
import pathlib

SCENARIOS = {'idle', 'auth', 'traffic', 'recovery'}
NUMBERS = ('pid', 'uptime_cs', 'rss_kib', 'hwm_kib', 'cpu_ticks', 'host_cpu_ticks', 'mem_available_kib')


def report(paths):
    groups = {}
    for path in paths:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('measurement file too large')
        samples = []
        for line in path.read_text(encoding='utf-8').splitlines():
            sample = json.loads(line)
            if sample.get('schema') != 1 or sample.get('evidence') != 'resource_sample' or sample.get('scenario') not in SCENARIOS:
                raise ValueError('unknown measurement schema/scenario')
            if any(type(sample.get(key)) is not int or not 0 <= sample[key] <= 2**53 - 1 for key in NUMBERS):
                raise ValueError('invalid measurement counter')
            if not isinstance(sample.get('startticks'), str) or not sample['startticks'].isdigit():
                raise ValueError('missing process identity')
            if sample['hwm_kib'] < sample['rss_kib']:
                raise ValueError('invalid peak memory')
            if samples:
                old = samples[-1]
                if (sample['pid'], sample['startticks'], sample['scenario']) != (old['pid'], old['startticks'], old['scenario']):
                    raise ValueError('process/scenario changed within measurement')
                if not 0 < sample['uptime_cs'] - old['uptime_cs'] <= 6500:
                    raise ValueError('non-monotonic boot clock or sample gap')
                if sample['cpu_ticks'] < old['cpu_ticks'] or sample['host_cpu_ticks'] <= old['host_cpu_ticks']:
                    raise ValueError('non-monotonic CPU counters')
            samples.append(sample)
        if len(samples) < 2:
            raise ValueError('insufficient samples')
        scenario = samples[0]['scenario']
        if scenario in groups:
            raise ValueError('duplicate scenario input')
        fractions = [(b['cpu_ticks'] - a['cpu_ticks']) / (b['host_cpu_ticks'] - a['host_cpu_ticks']) for a, b in zip(samples, samples[1:])]
        if any(value > 1 for value in fractions):
            raise ValueError('process CPU exceeds all host CPUs')
        groups[scenario] = {
            'samples': len(samples), 'duration_seconds': (samples[-1]['uptime_cs'] - samples[0]['uptime_cs']) / 100,
            'peak_rss_kib': max(s['rss_kib'] for s in samples), 'peak_hwm_kib': max(s['hwm_kib'] for s in samples),
            'minimum_available_kib': min(s['mem_available_kib'] for s in samples),
            'peak_fraction_all_cpu': max(fractions),
        }
    return {'schema': 1, 'scenarios': groups, 'missing_scenarios': sorted(SCENARIOS - groups.keys()),
            'qualification': False, 'reason': 'resource measurements alone do not prove throughput, safety or native platform acceptance'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('samples', type=pathlib.Path, nargs='+')
    args = parser.parse_args()
    try:
        print(json.dumps(report(args.samples), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Resource evidence rejected: {exc}\n')
