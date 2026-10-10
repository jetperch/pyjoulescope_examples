#!/usr/bin/env python3

# Copyright 2019 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Extract the current range from a Joulescope JLS capture.

This script opens a JLS capture and extracts the current range data.
The script can save the current range data to another format and plot the
data.  To use this script you will need Python 3.6+ installed on your machine.

To install the required dependencies:

    pip3 install joulescope matplotlib
    
To run this script and get help:

    python3 current_range_extract.py --help
    
Example to save to .txt file:

    python3 current_range_extract.py {my.jls} --out my.txt
    
Example to immediately plot the current range data:

    python3 current_range_extract.py {my.jls} --plot

"""


from joulescope.data_recorder import DataReader
import matplotlib.pyplot as plt
import argparse
import numpy as np
import sys


CHUNK_SAMPLES = 100_000        # process in chunks, so any file size fits in memory
PLOT_POINTS_MAX = 1_000_000    # plot longer captures as a min / max envelope


def get_parser():
    p = argparse.ArgumentParser(
        description='Extract the current range from a Joulescope JLS capture.')
    p.add_argument('filename',
                   help='The filename containing the JLS capture.')
    p.add_argument('--out', '-o',
                   help='The output filename')
    p.add_argument('--plot',
                   action='store_true',
                   help='Plot the current range')
    return p


def _plot(envelope, samples_per_point):
    f = plt.figure()
    ax = f.add_subplot(1, 1, 1)
    e = np.concatenate(envelope)
    x = np.arange(len(e)) * samples_per_point
    if samples_per_point == 1:
        ax.plot(x, e[:, 0])
    else:  # each point covers several samples, so show their range
        ax.fill_between(x, e[:, 0], e[:, 1], step='post')
        ax.set_xlabel(f'Sample ({samples_per_point} samples per point)')
    plt.show()
    plt.close(f)


def run():
    parser = get_parser()
    args = parser.parse_args()
    r = DataReader().open(args.filename)
    try:
        print(r.summary_string())
        out_type = None if args.out is None else args.out.split('.')[-1].lower()
        if out_type not in [None, 'csv', 'txt', 'npy']:
            print('Unsupported save type: %s', args.out)
            return 1
        s_start, s_stop = r.sample_id_range
        n = s_stop - s_start
        samples_per_point = max(1, -(-n // PLOT_POINTS_MAX))  # ceil
        chunk = max(1, CHUNK_SAMPLES // samples_per_point) * samples_per_point
        envelope = []  # (min, max) for each plotted point
        out = None
        try:
            for k0 in range(s_start, s_stop, chunk):
                k1 = min(k0 + chunk, s_stop)
                d = r.samples_get(k0, k1, units='samples', fields=['current_range'])
                current_range = d['signals']['current_range']['value']
                if out_type in ['csv', 'txt']:
                    if out is None:
                        out = open(args.out, 'wt')
                    np.savetxt(out, current_range, fmt='%d', delimiter=',')
                elif out_type == 'npy':
                    if out is None:  # written in place, so it never needs the whole capture in memory
                        out = np.lib.format.open_memmap(args.out, mode='w+',
                                                        dtype=current_range.dtype, shape=(n,))
                    out[k0 - s_start:k1 - s_start] = current_range
                if args.plot:
                    m = -(-len(current_range) // samples_per_point) * samples_per_point
                    padded = np.pad(current_range, (0, m - len(current_range)), mode='edge')
                    blocks = padded.reshape((-1, samples_per_point))
                    envelope.append(np.stack([blocks.min(axis=1), blocks.max(axis=1)], axis=1))
        finally:
            if isinstance(out, np.memmap):
                out.flush()
            elif out is not None:
                out.close()
    finally:
        r.close()

    if args.plot and envelope:
        _plot(envelope, samples_per_point)
    return 0


if __name__ == '__main__':
    sys.exit(run())

