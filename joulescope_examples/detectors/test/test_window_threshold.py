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

from ..window_threshold import WindowThresholdDetector
import numpy as np
import unittest


class TestWindowThresholdDetector(unittest.TestCase):

    def test_empty(self):
        d = WindowThresholdDetector(1.0, 100)
        self.assertFalse(d.process(np.array([])))

    def test_trivial_positive(self):
        d = WindowThresholdDetector(1.0, 1)
        self.assertFalse(d.process(np.array([0])))
        self.assertFalse(d.process(np.array([0.99])))
        self.assertTrue(d.process(np.array([1.0])))
        self.assertEqual(1, len(d))
        self.assertTrue(d.process(np.array([1.1])))
        self.assertEqual(2, len(d))
        self.assertFalse(d.process(np.array([0])))
        self.assertFalse(d.process(np.array([-2])))

    def test_trivial_negative(self):
        d = WindowThresholdDetector(-1.0, 1)
        self.assertFalse(d.process(np.array([0])))
        self.assertFalse(d.process(np.array([-0.99])))
        self.assertTrue(d.process(np.array([-1.0])))
        self.assertTrue(d.process(np.array([-1.1])))
        self.assertFalse(d.process(np.array([0])))
        self.assertFalse(d.process(np.array([2])))

    def test_pos(self):
        d = WindowThresholdDetector(1.0, 3)
        self.assertFalse(d.process(np.array([1.0])))
        self.assertEqual(1, len(d))
        self.assertFalse(d.process(np.array([1.0])))
        self.assertEqual(2, len(d))
        self.assertTrue(d.process(np.array([1.0])))
        self.assertEqual(3, len(d))
        self.assertTrue(d.process(np.array([1.0])))
        self.assertEqual(4, len(d))

        d.clear()
        self.assertEqual(0, len(d))
        self.assertFalse(d.process(np.array([1.0])))
        self.assertFalse(d.process(np.array([1.0])))
        self.assertTrue(d.process(np.array([1.0])))

    def test_zeros(self):
        d = WindowThresholdDetector(1.0, 10)
        x = np.zeros(100)
        self.assertFalse(d.process(x))

    def test_set(self):
        d = WindowThresholdDetector(1.0, 10)
        x = np.ones(100)
        self.assertTrue(d.process(x))

    def test_exact_at_start(self):
        d = WindowThresholdDetector(1.0, 10)
        x = np.zeros(100)
        x[0:10] = 1.0
        self.assertTrue(d.process(x))

    def test_exact_at_middle(self):
        d = WindowThresholdDetector(1.0, 10)
        x = np.zeros(100)
        x[10:20] = 1.0
        self.assertTrue(d.process(x))

    def test_exact_at_end(self):
        d = WindowThresholdDetector(1.0, 10)
        x = np.zeros(100)
        x[90:] = 1.0
        self.assertTrue(d.process(x))

    def test_carry_over(self):
        d = WindowThresholdDetector(1.0, 10)
        x1 = np.zeros(100)
        x1[95:] = 1.0
        self.assertFalse(d.process(x1))
        x2 = np.zeros(100)
        x2[:5] = 1.0
        self.assertTrue(d.process(x2))
        self.assertFalse(d.process(np.zeros(100)))

    def test_multiple(self):
        d = WindowThresholdDetector(1.0, 10)
        x1 = np.zeros(100)
        x1[10:25] = 1.0
        x1[50:75] = 1.0
        x1[95:] = 1.0
        self.assertTrue(d.process(x1))
        self.assertEqual(5, len(d))
        x2 = np.zeros(100)
        x2[:5] = 1.0
        self.assertTrue(d.process(x2))

