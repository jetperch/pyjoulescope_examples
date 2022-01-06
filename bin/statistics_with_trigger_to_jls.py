#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2019-2022 Jetperch LLC
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

"""Capture statistics data, analyze for trigger, and capture full-rate data
to JLS v2 file on trigger."""

from joulescope import scan_require_one
from joulescope.jls_v2_writer import SIGNALS, _signals_validator, _sampling_rate_validator
from pyjls import Writer, SourceDef, SignalDef, SignalType, DataType
from joulescope.units import duration_to_seconds
import argparse
import datetime
import numpy as np
import signal
import time


def now_str():
    d = datetime.datetime.utcnow()
    s = d.strftime('%Y%m%d_%H%M%S')
    return s


class CustomJlsWriter:

    def __init__(self, device_info, filename, signals=None):
        """Create a new JLS file writer instance.

        :param device_info: The Joulescope device info with extra 'host' key.
        :param filename: The output ".jls" filename.
        :param signals: The signals to record as either a list of string names
            or a comma-separated string.  The supported signals include
            ['current', 'voltage', 'power']

        This class implements joulescope.driver.StreamProcessApi and may also
        be used as a context manager.

        This class modifies joulescope.jls_v2_writer.JlsWriter to used cached
        device information.  As of 2022 Jan 6, the call to device.info()
        while already streaming throws an exception.
        """
        self._device_info = device_info
        self._filename = filename
        if signals is None:
            signals = ['current', 'voltage']
        signals = _signals_validator(signals)
        self._signals = signals
        self._wr = None
        self._idx = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self):
        """Open and configure the JLS writer file."""
        self.close()
        info = self._device_info
        sampling_rate = info['host']['sampling_frequency']
        sampling_rate = _sampling_rate_validator(sampling_rate)

        source = SourceDef(
            source_id=1,
            name=info['host']['name'],
            vendor='Jetperch',
            model=info['ctl']['hw'].get('model', 'JS110'),
            version=info['ctl']['hw'].get('rev', '-'),
            serial_number=info['ctl']['hw']['sn_mfg'],
        )

        wr = Writer(self._filename)
        try:
            wr.source_def_from_struct(source)
            for s in self._signals:
                idx, units = SIGNALS[s]
                s_def = SignalDef(
                    signal_id=idx,
                    source_id=1,
                    signal_type=SignalType.FSR,
                    data_type=DataType.F32,
                    sample_rate=sampling_rate,
                    name=s,
                    units=units,
                )
                wr.signal_def_from_struct(s_def)

        except Exception:
            wr.close()
            raise

        self._wr = wr
        return wr

    def close(self):
        """Finalize and close the JLS file."""
        wr, self._wr = self._wr, None
        if wr is not None:
            wr.close()

    def stream_notify(self, stream_buffer):
        """Handle incoming stream data.

        :param stream_buffer: The :class:`StreamBuffer` instance which contains
            the new data from the Joulescope.
        :return: False to continue streaming.
        """
        # called from USB thead, keep fast!
        # long-running operations will cause sample drops
        start_id, end_id = stream_buffer.sample_id_range
        if self._idx is None and start_id != end_id:
            self._idx = start_id
        if self._idx < end_id:
            data = stream_buffer.samples_get(self._idx, end_id, fields=self._signals)
            for s in self._signals:
                x = np.ascontiguousarray(data['signals'][s]['value'])
                idx = SIGNALS[s][0]
                self._wr.fsr_f32(idx, self._idx, x)
            self._idx = end_id
        return False



class StatisticsWithTrigger:

    def __init__(self, device, duration=120.0, signals='current,voltage'):
        self._device = device
        info = device.info()
        info['host'] = {
            'name': str(device),
            'sampling_frequency': device.parameter_get('sampling_frequency'),
            'calibration': device.calibration,
        }
        self._device_info = info
        self._duration = duration
        self._signals = signals
        self._base_filename = now_str()
        self._csv_filename = self._base_filename + '.csv'
        self._csv_file = open(self._csv_filename, 'wt')
        self._trigger = False
        self._jls_writer = None
        self._jls_end = None
        self._jls_idx = 0

    def on_statistics(self, stats):
        """The function called for each statistic update.

        :param stats: The statistics data structure.
        """
        t = stats['time']['range']['value'][0]
        i = stats['signals']['current']['µ']['value']
        v = stats['signals']['voltage']['µ']['value']
        p = stats['signals']['power']['µ']['value']
        c = stats['accumulators']['charge']['value']
        e = stats['accumulators']['energy']['value']
        if self._csv_file:
            self._csv_file.write(f'{t:.1f},{i:.9f},{v:.3f},{p:.9f},{c:.9f},{e:.9f}\n')

        # todo replace with custom trigger code
        if not self._trigger and i > 0.001:
            print('trigger')
            self._trigger = True

    def _capture_start(self):
        print('jls capture start')
        fname = f'{self._base_filename}_{self._jls_idx:04d}.jls'
        self._jls_writer = CustomJlsWriter(self._device_info, fname, self._signals)
        self._jls_writer.open()
        self._jls_idx += 1

    def _capture_stop(self):
        jls_writer, self._jls_writer = self._jls_writer, None
        if jls_writer is not None:
            print('jls capture stop')
            jls_writer.close()
        self._trigger = False

    def stream_notify(self, stream_buffer):
        # called from USB thead, keep fast!
        # long-running operations will cause sample drops
        start_id, end_id = stream_buffer.sample_id_range
        if self._trigger and self._jls_writer is None:
            self._capture_start()
            self._jls_end = end_id + int(self._device.sampling_frequency * self._duration)
        if self._jls_writer is not None:
            self._jls_writer.stream_notify(stream_buffer)
            if end_id >= self._jls_end:
                self._capture_stop()
        return False

    def close(self):
        f, self._csv_file = self._csv_file, None
        if f is not None:
            f.close()
        if self._jls_writer is not None:
            self._jls_writer.close()


def get_parser():
    p = argparse.ArgumentParser(
        description='Capture Joulescope statistics and trigger to capture full-rate data to JLS v2.')
    p.add_argument('--duration',
                   type=duration_to_seconds,
                   help='The full-rate capture duration in float seconds. '
                   + 'Add a suffix for other units: s=seconds, m=minutes, h=hours, d=days')
    p.add_argument('--signals',
                   default='current,voltage',
                   help='The comma-separated list of signals to capture which include current, voltage, power. '
                   + 'Defaults to current,voltage')
    return p


def run():
    _quit = False

    def stop_fn(*args, **kwargs):
        nonlocal _quit
        _quit = True

    args = get_parser().parse_args()
    signal.signal(signal.SIGINT, stop_fn)  # also quit on CTRL-C
    device = scan_require_one(config='auto')
    try:
        device.parameter_set('buffer_duration', 3.0)
        device.parameter_set('reduction_frequency', '1 Hz')
        device.open()
        s = StatisticsWithTrigger(device, duration=args.duration, signals=args.signals)
        device.statistics_callback_register(s.on_statistics)
        device.stream_process_register(s)
        device.parameter_set('i_range', 'auto')
        device.parameter_set('v_range', '15V')
        device.start()
        while not _quit:
            device.status()
            time.sleep(0.1)
        device.stop()

    finally:
        device.close()
        s.close()


if __name__ == '__main__':
    run()
