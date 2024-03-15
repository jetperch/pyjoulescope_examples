# Copyright 2021-2024 Jetperch LLC
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
import signal

from pyjls import Reader, SignalType, SummaryFSR
import argparse
import numpy as np
import os
import sys


def get_parser():
    p = argparse.ArgumentParser(
        description='Display energy plot from JLS file by integrating the power signal.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help='Display verbose information.')
    p.add_argument('--sample_count',
                   type=int,
                   default=1_000_000,
                   help='The number of samples to display')
    p.add_argument('infile',
                   help='JLS input filename')
    p.add_argument('--out',
                   help='The output filename path.')
    p.add_argument('--show',
                   action='store_true',
                   help='Display the plot.')
    return p


def run():
    args = get_parser().parse_args()
    try:
        import matplotlib.pyplot as plt
    except (ModuleNotFoundError, ImportError):
        print('Could not import matplotlib.  Install using:')
        print(f'{sys.executable} -m pip install -U matplotlib')
        return 1

    def verbose(msg):
        if args.verbose:
            print(msg)

    verbose(f'Opening JLS file {args.infile}')
    with Reader(args.infile) as r:
        try:
            signal = r.signal_lookup('power')
        except ValueError:
            print('Could not find power signal.  For JLS info, type:')
            print(f'{sys.executable} -m pyjls info {args.infile}')
            return 1
        if signal.signal_type != SignalType.FSR:
            print('Signal type mismatch')
            return 1
        incr = max(1, signal.length // args.sample_count)
        length = signal.length // incr
        dt = incr / signal.sample_rate

        verbose(f'Extract data: dt={dt} s, incr={incr}, length={length} | {incr * length} of {signal.length} samples')
        data = r.fsr_statistics(signal.signal_id, 0, incr, length)
        x = np.arange(0, length, dtype=np.float64) * dt
        y = np.cumsum(data[:, SummaryFSR.MEAN]) * dt  # Euler integration

    verbose(f'Create plot')
    f = plt.figure()
    ax = f.add_subplot(1, 1, 1)
    ax.set_title(os.path.basename(args.infile))
    ax.grid(True)
    ax.plot(x, y)
    ax.set_xlabel('Time (seconds)')
    ax.set_ylabel('Energy (J)')

    if args.out is None or args.show:
        verbose(f'Show plot')
        plt.show()
    if args.out is not None:
        verbose(f'Save plot to {args.out}')
        f.savefig(args.out)
    return 0


if __name__ == '__main__':
    sys.exit(run())
