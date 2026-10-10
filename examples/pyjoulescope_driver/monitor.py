#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2023 Jetperch LLC
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

"""Perform long-term current monitoring.

CAUTION: UNDER DEVELOPMENT
See https://forum.joulescope.com/t/exported-jls-data-to-an-xlsx-file/580

Inspect current data for errant conditions.  On an errant condition,
record data for analysis.  For now, records 50 Hz statistics
data to both a JLS v2 file and an Excel XLSX file.

See https://github.com/jetperch/jls
See https://github.com/jetperch/joulescope_driver
"""

from pyjls import Writer, SignalType, DataType
from pyjoulescope_driver import Driver, device_filter
import argparse
import openpyxl
import sys
import time
import numpy as np
import datetime


# todo should probably be part of pyjoulescope_driver
EPOCH = datetime.datetime(2018, 1, 1, tzinfo=datetime.timezone.utc).timestamp()  # seconds
SECOND = (1 << 30)


def _time64_to_datetime(t64) -> datetime.datetime:
    ts = (t64 / SECOND) + EPOCH
    return datetime.datetime.fromtimestamp(ts)


def _time64_to_filename(t64, suffix=None) -> str:
    suffix = '.jls' if suffix is None else str(suffix)
    dt = _time64_to_datetime(t64)
    timestamp_str = dt.strftime('%Y%m%d_%H%M%S')
    return f'{timestamp_str}{suffix}'


class Monitor:
    ST_SCAN = 0
    ST_CAPTURE = 1

    def __init__(self, driver, device_prefix):
        self._driver = driver
        self._device_prefix = device_prefix
        self._fs = 2_000_000 if device_prefix.model == 'js110' else 1_000_000  # Hz
        self._summary_fs = 50  # Hz
        self._summary_sample_id = 0
        self._summary_sample_id_offset = 0
        self._on_statistic_fn = self._on_statistic
        self._end_count = 0
        self._end_count_threshold = 2 * self._summary_fs  # 2 seconds
        self._state = self.ST_SCAN
        self._i_threshold = 0.001  # 1 mA
        self._detail_jls = None
        self._summary_jls = None
        self._summary_xlsx = None
        self._summary_xlsx_filename = None
        self._stat_buffer = []

    def _open_jls(self, filename, fs):
        """Open a JLS v2 file for the connected Joulescope.

        :param filename: The file path for the JLS write.
        :param fs: The sampling frequency in Hertz.
        :return: The open JLS file ready for writing.
        """
        _, model, serial_number = self._device_prefix.split('/')
        model = model.upper()
        wr = Writer(filename)
        wr.source_def(
            source_id=1,
            name=f'{model}-{serial_number}',
            vendor='Jetperch',
            model=model,
            version='',
            serial_number=serial_number,
        )
        wr.signal_def(
            signal_id=1,
            source_id=1,
            signal_type=SignalType.FSR,
            data_type=DataType.F32,
            sample_rate=fs,
            name='current',
            units='A',
        )
        wr.signal_def(
            signal_id=2,
            source_id=1,
            signal_type=SignalType.FSR,
            data_type=DataType.F32,
            sample_rate=fs,
            name='voltage',
            units='V',
        )
        return wr

    def _on_statistic(self, topic, value):
        """Callback for 50 Hz statistics."""
        # print(value)
        utc = value['time']['utc']['value'][0]
        i_avg = value['signals']['current']['avg']['value']
        v_avg = value['signals']['voltage']['avg']['value']
        self._stat_buffer.append((utc, i_avg, v_avg))
        self._stat_buffer = self._stat_buffer[-self._summary_fs:]
        # print(f'{i_avg} {v_avg}')
        if self._state == self.ST_SCAN:
            self._end_count = 0
            self._summary_sample_id = 0
            self._summary_sample_id_offset = 0
            if i_avg >= self._i_threshold:
                dt = _time64_to_datetime(utc).isoformat()
                print(f'{dt}: Current threshold exceeded.  Start capture')
                self._state = self.ST_CAPTURE
                summary_jls_filename = _time64_to_filename(utc, '_summary.jls')
                self._summary_jls = self._open_jls(summary_jls_filename, self._summary_fs)
                utc_v = self._stat_buffer[0][0]
                self._summary_jls.utc(1, 0, utc_v)
                self._summary_jls.utc(2, 0, utc_v)
                i_array = np.array([x[1] for x in self._stat_buffer], dtype=np.float32)
                v_array = np.array([x[2] for x in self._stat_buffer], dtype=np.float32)
                self._summary_jls.fsr_f32(1, 0, i_array)
                self._summary_jls.fsr_f32(2, 0, v_array)
                self._summary_sample_id = len(self._stat_buffer)
                self._summary_sample_id_offset = - (self._summary_sample_id - 1)

                self._summary_xlsx_filename = _time64_to_filename(utc, '_summary.xlsx')
                self._summary_xlsx = openpyxl.Workbook()
                worksheet = self._summary_xlsx.active
                worksheet.append(['SampleID', 'Current A', 'Voltage V'])
                sample_id_zero = len(self._stat_buffer) - 1
                for idx, (_, i_v, v_v) in enumerate(self._stat_buffer):
                    row = idx + 2
                    worksheet.cell(row=row, column=1, value=idx - sample_id_zero)
                    worksheet.cell(row=row, column=2, value=i_v)
                    worksheet.cell(row=row, column=3, value=v_v)
            return

        self._summary_jls.fsr_f32(1, self._summary_sample_id, np.array([i_avg], dtype=np.float32))
        self._summary_jls.fsr_f32(2, self._summary_sample_id, np.array([v_avg], dtype=np.float32))
        row = self._summary_sample_id + 2
        if self._summary_xlsx is not None:
            worksheet = self._summary_xlsx.active
            worksheet.cell(row=row, column=1, value=self._summary_sample_id + self._summary_sample_id_offset)
            worksheet.cell(row=row, column=2, value=i_avg)
            worksheet.cell(row=row, column=3, value=v_avg)

        if self._summary_sample_id > (1024 * 1024 - 8):
            self._summary_xlsx_close()

        if i_avg < self._i_threshold:
            self._end_count += 1
            if self._end_count >= self._end_count_threshold:
                self._summary_jls.utc(1, self._summary_sample_id, utc)
                self._summary_jls.utc(2, self._summary_sample_id, utc)
                dt = _time64_to_datetime(utc).isoformat()
                print(f'{dt}: Current returned to normal.  End capture')
                self._end_count = 0
                self._state = self.ST_SCAN
                self._summary_jls.close()
                self._summary_jls = None
                self._summary_xlsx_close()

        self._summary_sample_id += 1

    def _summary_xlsx_close(self):
        if self._summary_xlsx is not None:
            self._summary_xlsx.save(self._summary_xlsx_filename)
            self._summary_xlsx = None

    def device_publish(self, topic, value):
        self._driver.publish(f'{self._device_prefix}/{topic}', value)

    def open(self):
        self._driver.open(self._device_prefix)
        self.device_publish('h/fs', self._fs)
        self.device_publish('s/stats/scnt', self._fs // self._summary_fs)
        if self._device_prefix.model == 'js110':
            self.device_publish('s/i/range/select', 'auto')
            self.device_publish('s/v/range/select', '15 V')
            # the JS110 computes these statistics on the host from the sample streams
            self.device_publish('s/i/ctrl', 1)
            self.device_publish('s/v/ctrl', 1)
        else:  # the JS220 and JS320 compute statistics on the instrument
            self.device_publish('s/i/range/mode', 'auto')
            self.device_publish('s/v/range/select', '15 V')
            self.device_publish('s/v/range/mode', 'manual')  # as of 2023-03-24, auto not working well
        self.device_publish('s/stats/ctrl', 1)
        self._driver.subscribe(f'{self._device_prefix}/s/stats/value', ['pub'], self._on_statistic_fn)

    def close(self):
        try:
            if self._device_prefix.model == 'js110':
                self.device_publish('s/i/ctrl', 0)
                self.device_publish('s/v/ctrl', 0)
            self.device_publish('s/stats/ctrl', 0)
        except RuntimeError as ex:  # such as unplugged, which already stopped it
            print(f'Could not stop {self._device_prefix}: {ex}')
        self._driver.unsubscribe(f'{self._device_prefix}/s/stats/value', self._on_statistic_fn)
        self._driver.close(self._device_prefix)
        if self._summary_jls is not None:
            self._summary_jls.close()
        self._summary_xlsx_close()


def get_parser():
    p = argparse.ArgumentParser(
        description='Perform long-term current monitoring.')
    p.add_argument('--device', '-d',
                   help='The Joulescope to use, such as "js220", "000415" or "js220-000415".')
    return p


def run():
    args = get_parser().parse_args()
    with Driver() as driver:
        try:
            device_prefix = driver.find_one_device(args.device, brand='joulescope')
        except device_filter.DeviceFilterError as ex:
            print(ex)
            if len(ex.matches) > 1:
                print('Use "--device" to specify the desired device.')
            return 1
        monitor = Monitor(driver, device_prefix)
        monitor.open()
        removed = []

        def on_remove(topic, value):  # an unplugged device sends no more data, so stop
            if value in [device_prefix]:
                removed.append(value)

        try:
            with driver.subscribe('@/!remove', 'pub', on_remove):
                while not removed:
                    time.sleep(0.010)
        except KeyboardInterrupt:
            pass
        monitor.close()
        if removed:
            print(f'{removed[0]} removed: stop')
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(run())
