#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

"""Plot calibrated data"""

import matplotlib.pyplot as plt
import matplotlib.collections
import numpy as np


def plot_axis(axis, x, y, label=None):
    if label is not None:
        axis.set_ylabel('Current (A)')
    axis.grid(True)

    axis.plot(x, y)

    # draw vertical lines at start/end of NaN region
    yvalid = np.isfinite(y)
    for line in x[np.nonzero(np.diff(yvalid))]:
        axis.axvline(line, color='red')

    # Fill each NaN region, too
    ymin, ymax = np.min(y[yvalid]), np.max(y[yvalid])
    collection = matplotlib.collections.BrokenBarHCollection.span_where(
        x, ymin=ymin, ymax=ymax, where=np.logical_not(yvalid), facecolor='red', alpha=0.5)
    axis.add_collection(collection)
    return axis


def plot_iv(data, sampling_frequency, show=None):
    x = np.arange(len(data), dtype=np.float)
    x *= 1.0 / sampling_frequency
    f = plt.figure()

    ax_i = f.add_subplot(2, 1, 1)
    plot_axis(ax_i, x, data[:, 0], label='Current (A)')
    ax_v = f.add_subplot(2, 1, 2, sharex=ax_i)
    plot_axis(ax_v, x, data[:, 1], label='Voltage (V)')

    if show is None or bool(show):
        plt.show()
        plt.close(f)


def print_stats(data, sampling_frequency):
    duration = len(data) / sampling_frequency
    finite = np.count_nonzero(np.isfinite(data))
    total = np.prod(data.shape)
    nonfinite = total - finite
    print(f'found {nonfinite} NaN out of {total} samples ({duration:.3f} seconds)')
