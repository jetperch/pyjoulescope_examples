<!--
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
-->

# Legacy examples

These examples still run, but they show older patterns or JS110-only
features.  Start new code from the other example directories instead.

| Example | Why it is here | Instead, see |
| ------- | -------------- | ------------ |
| `capture.py` | Wraps the driver's record entry point | `python -m pyjoulescope_driver record out.jls` |
| `capture_jls_v1.py` | Writes the JLS v1 format | `../joulescope/capture_jls.py` |
| `current_range_extract.py` | Reads JLS v1 files | `../pyjls/jls_export_points.py` |
| `current_ranging_filter.py` | JS110 only | |
| `energy_printer_sensor.py` | Sensor statistics only differ on the JS110 | `../joulescope/energy_printer.py` |
| `gpi_synchronized.py`, `gpio.py`, `trigger.py`, `windowed_accum.py` | Use the JS110 GPI-in-LSB parameters | `../pyjoulescope_driver/gpi_region.py` |
| `jls_recode.py` | Reads and writes JLS v1 files | |
| `statistics_v1.py` | Superseded | `../joulescope/statistics.py` |
