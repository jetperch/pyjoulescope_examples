#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import numpy as np
import sys
import math
import matplotlib.pyplot as plt
from joulescope.data_recorder import DataReader
from pyjls import Reader, SummaryFSR
from joulescope.view import data_array_to_update
from joulescope.units import unit_prefix


# Developed for https://forum.joulescope.com/t/automation-of-plotting-long-term-records/415
_V1_PREFIX = bytes([0xd3, 0x74, 0x61, 0x67, 0x66, 0x6d, 0x74, 0x20, 0x0d, 0x0a, 0x20, 0x0a, 0x20, 0x20, 0x1a, 0x1c])
_V2_PREFIX = bytes([0x6a, 0x6c, 0x73, 0x66, 0x6d, 0x74, 0x0d, 0x0a, 0x20, 0x0a, 0x20, 0x1a, 0x20, 0x20, 0xb2, 0x1c])

def get_parser():
    p = argparse.ArgumentParser(
        description='Load a JLS file and generate an image plot.')
    p.add_argument('input',
                   help='The input filename path.')
    p.add_argument('--out',
                   help='The output filename path.')
    p.add_argument('--stats',
                   action='store_true',
                   help='Display statistics on the plot.')
    p.add_argument('--show',
                   action='store_true',
                   help='Display the plot.')
    p.add_argument('--sample_count',
                   type=int,
                   default=1000,
                   help='The number of samples to display')
    return p


# Statistics formatting copied from joulescope_ui.widgets.waveform.signal_statistics
def _si_format(names, values, units):
    results = []
    if units is None:
        units = ''
    if len(values):
        values = np.array(values)
        max_value = float(np.max(np.abs(values)))
        _, prefix, scale = unit_prefix(max_value)
        scale = 1.0 / scale
        if not len(prefix):
            prefix = '&nbsp;'
        units_suffix = f'{prefix}{units}'
        for lbl, v in zip(names, values):
            v *= scale
            if abs(v) < 0.000005:  # minimum display resolution
                v = 0
            v_str = ('%+6f' % v)[:8]
            results.append('%s=%s %s' % (lbl, v_str, units_suffix))
    return results


def si_format(labels):
    results = []
    if not len(labels):
        return results
    units = None
    values = []
    names = []
    for name, d in labels.items():
        value = float(d['value'])
        if name == 'σ2':
            name = 'σ'
            value = math.sqrt(value)
        if d['units'] != units:
            results.extend(_si_format(names, values, units))
            units = d['units']
            values = [value]
            names = [name]
        else:
            values.append(value)
            names.append(name)
    results.extend(_si_format(names, values, units))
    return results


def run():
    args = get_parser().parse_args()
    with open(args.input, 'rb') as f:
        prefix = f.read(16)
    if prefix == _V2_PREFIX:
        print(f'Reading JLS v2: {args.input}')
        r = Reader(args.input)
        signals = [s for s in r.signals.values() if s.name == 'current']
        if not len(signals):
            print('"current" signal not found')
            return 1
        s = signals[0]
        incr = s.length // args.sample_count
        length = s.length // incr
        data = r.fsr_statistics(signals[0].signal_id, 0, incr, length)
        y = data[:, 0]
        x = np.arange(0, len(y), dtype=np.float64) * (incr / s.sample_rate)
        z = r.fsr_statistics(signals[0].signal_id, 0, s.length, 1)[0, :]
        stats = {
            'µ': {'value': z[SummaryFSR.MEAN], 'units': s.units},
            'σ': {'value': z[SummaryFSR.STD], 'units': s.units},
            'min': {'value': z[SummaryFSR.MIN], 'units': s.units},
            'max': {'value': z[SummaryFSR.MAX], 'units': s.units},
            'p2p': {'value': z[SummaryFSR.MAX] - z[SummaryFSR.MIN], 'units': s.units},
            '∫': {'value': z[SummaryFSR.MEAN] * x[-1], 'units': 'C'},
        }
        s_str = [f't = {x[-1]:.3} s'] + si_format(stats)

    elif prefix == _V1_PREFIX:
        print(f'Reading JLS v1: {args.input}')
        r = DataReader().open(args.input)
        start_idx, stop_idx = r.sample_id_range
        d_idx = stop_idx - start_idx
        f = r.sampling_frequency
        incr = d_idx // args.sample_count
        data = r.data_get(start_idx, stop_idx, incr, units='samples')

        x = np.linspace(0.0, d_idx / f, len(data), dtype=np.float64)
        x_limits = [x[0], x[-1]]
        d = data_array_to_update(x_limits, x, data)
        s = r.statistics_get(start_idx, stop_idx)
        s_str = [f't = {x[-1]:.3} s']
        s_str += si_format(s['signals']['current'])
        y = d['signals']['current']['µ']['value']
    else:
        print('Unsupported file format')
        return 1

    f = plt.figure()
    ax_i = f.add_subplot(1, 1, 1)
    ax_i.set_title('Current vs Time')
    ax_i.grid(True)
    ax_i.plot(x, y)
    ax_i.set_xlabel('Time (seconds)')
    ax_i.set_ylabel('Current (A)')
    if args.stats:
        f.subplots_adjust(right=0.75)
        f.text(0.99, 0.85, '\n'.join(s_str), horizontalalignment='right', verticalalignment='top')
    if args.show:
        plt.show()
    if args.out:
        f.savefig(args.out)


if __name__ == '__main__':
    sys.exit(run())
