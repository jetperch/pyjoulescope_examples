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

from .interface import DetectorInterface
import numpy as np


class WindowThresholdDetector(DetectorInterface):

    def __init__(self, threshold, duration, name=None):
        """Analyze incoming samples exceeding a threshold for a duration.

        :param threshold: The signed threshold.
        :param duration: The duration in samples.
        :param name: The optional user-meaningful name for this detector
        """
        self._threshold = float(threshold)
        self._duration = int(duration)
        self._count = 0
        self._name = str(name)

    @property
    def name(self):
        return self._name

    def __len__(self):
        return self._count

    def clear(self):
        self._count = 0

    def process(self, samples):
        samples_len = len(samples)
        if 0 == samples_len:
            return
        if self._threshold > 0:
            w = (samples >= self._threshold)
        else:
            w = (samples <= self._threshold)
        if 1 == samples_len:
            if w[0]:
                count = self._count + 1
            else:
                count = 0
            count_next = count
        else:
            indices = np.where(np.diff(w) == True)[0] + 1
            indices = np.concatenate([[0], indices, [samples_len]])
            if w[0]:
                run_end = indices[1::2]
                lengths = run_end - indices[0:2*len(run_end):2]
                lengths[0] += self._count
                count = max(lengths)
            elif len(indices) > 2:
                run_end = indices[2::2]
                lengths = run_end - indices[1:1+2*len(run_end):2]
                count = max(lengths)
            else:
                count = 0
            if w[-1]:
                count_next = lengths[-1]
            else:
                count_next = 0
        rv = count >= self._duration
        self._count = count_next
        return rv


