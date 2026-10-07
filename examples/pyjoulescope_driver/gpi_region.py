#!/usr/bin/env python3
# Copyright 2024 Jetperch LLC
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

"""Extract signal summary data from regions delimited by general-purpose inputs."""

from pyjoulescope_driver import Driver, time64
import argparse
import logging
import sys
import time
import numpy as np


DATA_SIGNALS = ['i', 'v', 'p']
DETECT_SIGNALS = {
    '0': 'gpi/0',
    '1': 'gpi/1',
    '2': 'gpi/2',
    '3': 'gpi/3',
    'T': 'gpi/7',
}


def verbose(msg):
    pass


def get_parser():
    p = argparse.ArgumentParser(
        description='Extract signal summary data from regions delimited by general-purpose inputs.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help='Display verbose information.')
    p.add_argument('--gpi',
                   default='0',
                   help='The comma-separated list of GPI signals 0,1,2,3,T to monitor.')
    p.add_argument('--vref',
                   default='external',
                   choices=['external', '3v3'],
                   help='The Vref mode.')
    p.add_argument('--serial_number',
                   help='The serial number of the Joulescope to use.')
    return p


def _sample_id_range(buffer):
    """Get the sample ID range from a signal data buffer.

    :param buffer: The signal data buffer from a "!data" subscription.
    :return: The start, end sample_id range for the buffer.
    """
    start = buffer['sample_id']
    end = start + len(buffer['data']) * buffer['decimate_factor']
    return start, end


def _time_map(buffer, sample_id):
    """Compute the UTC time for a sample_id given a signal data buffer.

    :param buffer: The signal data buffer from a "!data" subscription.
    :param sample_id: The time as a sample id.
    :return: The time in time64 UTC format.
    """
    t = buffer['time_map']
    k = sample_id - t['offset_counter']
    k = (k * time64.SECOND) // int(t['counter_rate'])
    return k + t['offset_time']


class StatsCompute:
    """Compute running statistics over signal data buffers.

    :param sample_id_start: The starting sample ID for this statistics computation.
    """
    def __init__(self, sample_id_start):
        self.sample_id_start = sample_id_start
        self.sample_id_end = None
        self.sample_id_next = sample_id_start
        self.len = 0
        self.mean = 0
        self.var = 0
        self.min = None
        self.max = None

    @property
    def std(self):
        return np.sqrt(self.var)

    @property
    def is_complete(self):
        if self.sample_id_end is None:
            return False
        return self.sample_id_next >= self.sample_id_end

    def add(self, buffer):
        start, end = _sample_id_range(buffer)
        if self.sample_id_end is not None and start > self.sample_id_end:
            # verbose('buffer beyond region end, skip')
            return
        if end <= self.sample_id_next:
            # verbose('buffer before region, skip')
            return
        data = buffer['data']
        if self.sample_id_end is not None and self.sample_id_end < end:
            # verbose('buffer final, trim')
            end_idx = (self.sample_id_end - start) // buffer['decimate_factor']
            data = data[:end_idx]
        if self.sample_id_next > start:
            # verbose('buffer start, trim')
            start_idx = (self.sample_id_next - start) // buffer['decimate_factor']
            data = data[start_idx:]
        v_len = len(data)
        v_mean = np.mean(data)
        v_var = np.var(data)
        v_min = np.min(data)
        v_max = np.max(data)
        if self.len == 0:
            self.len = v_len
            self.mean = v_mean
            self.var = v_var
            self.min = v_min
            self.max = v_max
        else:
            t_len = self.len + v_len
            c_mean = (v_mean * v_len + self.mean * self.len) / t_len
            v_mean_diff = v_mean - c_mean
            p_mean_diff = self.mean - c_mean
            v = (v_len * (v_var + v_mean_diff ** 2) +
                 self.len * (self.var + p_mean_diff ** 2))
            v /= t_len
            self.len = t_len
            self.mean = c_mean
            self.var = v
            self.min = min(v_min, self.min)
            self.max = max(v_max, self.max)
        self.sample_id_next = end

    def to_csv(self):
        return f'{self.len},{self.mean},{self.std},{self.min},{self.max}'


class Region:
    """Compute statistics over a running region of interest.

    :param sample_id_start: The starting sample ID.
    :param utc_start: The starting time64 UTC time.
    """
    def __init__(self, sample_id_start, utc_start):
        self.samples = [sample_id_start, None]
        self.utc = [utc_start, None]
        self.stats = {}
        for data_signal in DATA_SIGNALS:
            self.stats[data_signal] = StatsCompute(sample_id_start)

    def complete(self, sample_id_end, utc_end):
        self.samples[-1] = sample_id_end
        self.utc[-1] = utc_end
        for data_signal in DATA_SIGNALS:
            self.stats[data_signal].sample_id_end = sample_id_end

    @property
    def is_complete(self):
        if self.samples[-1] is None:
            return False
        return all([x.is_complete for x in self.stats.values()])

    def to_csv(self):
        utc = [time64.as_datetime(u).isoformat() for u in self.utc]
        parts = [f'{self.samples[0]},{self.samples[1]},{utc[0]},{utc[1]}']
        for stat in self.stats.values():
            parts.append(stat.to_csv())
        return ','.join(parts)


class GpiRegionDetector:
    """Detect regions denoted by GPI and compute signal statistics.

    :param jsdrv: The Joulescope `Driver` instance.
    :param device_path: The Joulescope instrument device path.
    :param gpi: The list of GPI signals to process.
    """
    def __init__(self, jsdrv, device_path, gpi):
        self._detect = {}
        self._jsdrv = jsdrv
        self.device_path = device_path
        self.gpi = gpi
        self.open()

    def open(self):
        # CSV header
        stats = ['length', 'mean', 'std', 'min', 'max']
        parts = ['device,signal,sample_id_start,sample_id_end,utc_start,utc_end']
        for signal in DATA_SIGNALS:
            parts.extend([f'{signal}.{x}' for x in stats])
        print(','.join(parts))
        sys.stdout.flush()

        self._detect.clear()
        for signal in DETECT_SIGNALS.keys():
            if signal not in self.gpi:
                continue
            self._detect[signal] = {
                'prev': None,
                'regions': [],  # elements of Region.
                'buffer': None,
                'signals': {
                    'i': [],
                    'v': [],
                    'p': [],
                }
            }
        for t in DATA_SIGNALS + [DETECT_SIGNALS[x] for x in self._detect.keys()]:
            self._jsdrv.subscribe(f'{self.device_path}/s/{t}/!data', ['pub'], self._on_data, timeout=0)
            self._jsdrv.publish(f'{self.device_path}/s/{t}/ctrl', 1, timeout=0)

    def close(self):
        signals = DATA_SIGNALS + [DETECT_SIGNALS[x] for x in self._detect.keys()]
        last = len(signals) - 1
        for idx, t in enumerate(signals):
            self._jsdrv.unsubscribe(f'{self.device_path}/s/{t}/!data', self._on_data, timeout=0)
            self._jsdrv.publish(f'{self.device_path}/s/{t}/ctrl', 0, timeout=None if last else 0)

    def _on_data(self, topic, value):
        signal = topic.split('/')[-2]
        if signal in DATA_SIGNALS:
            # Add data signal to GPI detection buffers
            for detect in self._detect.values():
                detect['signals'][signal].append(value)
        else:
            if signal == '7':
                signal = 'T'
            try:
                detect = self._detect[signal]
            except KeyError:
                return

            # perform processing delayed by one buffer
            value, detect['buffer'] = detect['buffer'], value
            if value is None:
                return

            # process GPI data into regions for statistics extraction
            data = np.unpackbits(value['data'], bitorder='little')
            prev = detect['prev']
            if prev is None:
                prev = data[0]
            next = (prev + 1) & 1
            sample_id = value['sample_id']
            while len(data):
                idx = np.where(data == next)[0]
                if len(idx) == 0:
                    break
                idx = idx[0]
                sample_id += int(idx) * value['decimate_factor']
                if next == 1:  # start
                    verbose(f'{signal}: start {sample_id} {value}')
                    detect['regions'].append(Region(sample_id, _time_map(value, sample_id)))
                else:
                    if len(detect['regions']):
                        verbose(f'{signal}: stop {sample_id}')
                        region = detect['regions'][-1]
                        region.complete(sample_id, _time_map(value, sample_id))
                data = data[idx:]
                detect['prev'] = next
                next = (next + 1) & 1

            # process signal data
            gpi_sample_id_start, gpi_sample_id_end = _sample_id_range(value)
            for data_signal, buffers in detect['signals'].items():
                while len(buffers):
                    start, end = _sample_id_range(buffers[0])
                    if end >= gpi_sample_id_end:
                        break
                    buffer = buffers.pop(0)
                    for region in detect['regions']:
                        region.stats[data_signal].add(buffer)

            # process completed regions
            regions = detect['regions']
            while len(regions):
                region = regions[0]
                if not region.is_complete:
                    break
                regions.pop(0)
                print(f'{self.device_path},{signal},{region.to_csv()}')
                sys.stdout.flush()


def run():
    global verbose
    args = get_parser().parse_args()
    if args.verbose:
        verbose = lambda msg: print(msg)

    with Driver() as jsdrv:
        jsdrv.log_level = 'WARNING'

        verbose('Find the connected devices')
        device_paths = sorted(jsdrv.device_paths())
        if args.serial_number is not None:
            serial_number_suffix = '/' + args.serial_number.lower()
            device_paths = [p for p in device_paths if p.lower().endswith(serial_number_suffix)]
        if len(device_paths) == 0:
            print('Device not found')
            return 1
        verbose(f'Found devices: {device_paths}')

        verbose('Open and configure each device')
        handlers = []
        for device_path in device_paths:
            if 'js220' in device_path:
                jsdrv.open(device_path, mode='defaults')
                jsdrv.publish(f'{device_path}/s/i/range/mode', 'auto', timeout=0)
                jsdrv.publish(f'{device_path}/s/v/range/mode', 'auto', timeout=0)
                jsdrv.publish(f'{device_path}/c/gpio/vref', args.vref, timeout=0)
                handler = GpiRegionDetector(jsdrv, device_path, args.gpi.split(','))
                handlers.append(handler)
            else:
                print(f'Unsupported device {device_path}: ignore')
                continue

        verbose('Perform the detection')
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            verbose('Closing')
            for handler in handlers:
                handler.close()
                jsdrv.close(handler.device_path)
    return 0


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)s %(message)s', level=logging.INFO)
    sys.exit(run())
