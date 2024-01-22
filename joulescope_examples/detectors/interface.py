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

import abc


class DetectorInterface(metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def name(self):
        return '__interface__'

    @abc.abstractmethod
    def clear(self) -> None:
        """Reset the detector"""
        pass

    @abc.abstractmethod
    def process(self, samples) -> bool:
        """Process the next block of samples.

        :param samples: The numpy.ndarray of sample values
        """
        return False
