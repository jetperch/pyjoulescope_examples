# SPDX-FileCopyrightText: Copyright 2026 Jetperch LLC
# SPDX-License-Identifier: Apache-2.0
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

"""Generate JLS files with known contents for the offline tests.

The signals are exact, so tests can check computed values:

* current: CURRENT_LOW for the first half of each PERIOD, then CURRENT_HIGH.
* voltage: VOLTAGE, constant.
* power: current * voltage.
"""

import numpy as np


SAMPLE_RATE = 100_000   # Hz
DURATION = 2.0          # seconds
PERIOD = 0.1            # seconds
CURRENT_LOW = 0.001     # A
CURRENT_HIGH = 0.003    # A
VOLTAGE = 3.3           # V
CURRENT_MEAN = (CURRENT_LOW + CURRENT_HIGH) / 2
POWER_MEAN = CURRENT_MEAN * VOLTAGE
TIME64_SECOND = 1 << 30
UTC_START = 2191 * 86400 * TIME64_SECOND  # time64 for 2024-01-01T00:00:00Z
UTC_START_STR = '2024-01-01T00:00:00+00:00'
SERIAL_NUMBER = '000415'


def signals(sample_rate=SAMPLE_RATE, duration=DURATION):
    """Compute the signals.

    :return: The dict of signal name to float32 numpy array.
    """
    n = int(sample_rate * duration)
    period = int(sample_rate * PERIOD)
    high = (np.arange(n) % period) >= (period // 2)
    current = np.where(high, CURRENT_HIGH, CURRENT_LOW).astype(np.float32)
    voltage = np.full(n, VOLTAGE, dtype=np.float32)
    power = (current.astype(np.float64) * VOLTAGE).astype(np.float32)
    return {'current': current, 'voltage': voltage, 'power': power}


def summary(path):
    """Summarize a JLS v2 file.

    :param path: The JLS v2 file path.
    :return: The dict of signal name to dict with keys source, sample_rate,
        length, units and mean.
    """
    from pyjls import Reader, SignalType
    rv = {}
    with Reader(str(path)) as r:
        for s in r.signals.values():
            if s.signal_type != SignalType.FSR or s.signal_id == 0:
                continue
            mean = None
            if s.length:
                mean = float(r.fsr_statistics(s.signal_id, 0, s.length, 1)[0][0])
            rv[s.name] = {
                'source': r.sources[s.source_id].name,
                'sample_rate': s.sample_rate,
                'length': s.length,
                'units': s.units,
                'mean': mean,
            }
    return rv


def write_v2(path, sample_rate=SAMPLE_RATE, duration=DURATION, names=None):
    """Write a JLS v2 file like a JS220 capture.

    :param path: The output file path.
    :param sample_rate: The sample rate in Hz.
    :param duration: The duration in seconds.
    :param names: The signal names to write.  None writes current,
        voltage and power.
    :return: path.
    """
    from pyjls import Writer, SignalType, DataType
    data = signals(sample_rate, duration)
    names = ['current', 'voltage', 'power'] if names is None else names
    units = {'current': 'A', 'voltage': 'V', 'power': 'W'}
    with Writer(str(path)) as wr:
        wr.source_def(source_id=1, name=f'JS220-{SERIAL_NUMBER}', vendor='Jetperch',
                      model='JS220', version='1.0.0', serial_number=SERIAL_NUMBER)
        for idx, name in enumerate(names):
            signal_id = idx + 1
            wr.signal_def(signal_id=signal_id, source_id=1, signal_type=SignalType.FSR,
                          data_type=DataType.F32, sample_rate=sample_rate,
                          name=name, units=units[name])
            wr.utc(signal_id, 0, UTC_START)
            wr.fsr_f32(signal_id, 0, data[name])
            sample_id = len(data[name]) - 1
            wr.utc(signal_id, sample_id, UTC_START + (sample_id * TIME64_SECOND) // sample_rate)
    return path


def write_v1(path, sample_rate=SAMPLE_RATE, duration=DURATION):
    """Write a JLS v1 file like a JS110 capture.

    :param path: The output file path.
    :param sample_rate: The sample rate in Hz.
    :param duration: The duration in seconds.
    :return: path.
    """
    from joulescope.data_recorder import DataRecorder
    from joulescope.v0.calibration import Calibration
    data = signals(sample_rate, duration)
    n = len(data['current'])
    zeros = np.zeros(n, dtype=np.float32)
    current_range = np.full(n, 4, dtype=np.float32)
    calibration = Calibration()  # like a JS110 capture, which always has one
    calibration.data = calibration.save(bytes([0] * 32))
    recorder = DataRecorder(str(path), calibration=calibration)
    try:
        recorder.insert({
            'time': {
                'sampling_frequency': {'value': sample_rate, 'units': 'Hz'},
                'sample_id_range': {'value': [0, n], 'units': 'samples'},
                'samples': {'value': n, 'units': 'samples'},
            },
            'signals': {
                'current': {'value': data['current'], 'units': 'A'},
                'voltage': {'value': data['voltage'], 'units': 'V'},
                'power': {'value': data['power'], 'units': 'W'},
                'current_range': {'value': current_range, 'units': ''},
                'current_lsb': {'value': zeros, 'units': ''},
                'voltage_lsb': {'value': zeros, 'units': ''},
            },
        })
        recorder.insert(None)  # flush the final partial block
    finally:
        recorder.close()
    return path
