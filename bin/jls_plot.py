#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import numpy as np
import sys
import math
import matplotlib.pyplot as plt
from joulescope.data_recorder import DataReader
from joulescope.view import data_array_to_update
from joulescope.units import unit_prefix


# Developed for https://forum.joulescope.com/t/automation-of-plotting-long-term-records/415


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

    f = plt.figure()
    ax_i = f.add_subplot(1, 1, 1)
    ax_i.set_title('Current vs Time')
    ax_i.grid(True)
    ax_i.plot(x, d['signals']['current']['µ']['value'])
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
