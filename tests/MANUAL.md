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

# Manual tests

The automated tests cannot yet unplug an instrument, reboot the host, wire
the GPIO, or apply a load.  Run these by hand when an example changes in a
way they cover, on each model that the example supports.  Automate an item
once the bench gains the hardware, such as a USB power switch.

Paths use the historical `bin/` names.


## Unplug and replug

Start the example, unplug the instrument, wait 5 seconds, then plug it back
in.

| Example | Expected on unplug | Expected on replug |
| ------- | ------------------ | ------------------ |
| `energy_printer_host.py` | exits | n/a |
| `downsample_logging.py` | keeps running, logs `DEVICE : CLOSE` | resumes logging to the same CSV file, logs `DEVICE : OPEN` |
| `downsample_logging.py`, started with no instrument | keeps waiting | starts logging |
| `capture_jls_v2.py`, `capture_all.py` | exits, the JLS file is readable | n/a |


## Host reboot

1. Start `downsample_logging.py` with an instrument and a load.
2. Reboot the host or kill the process.
3. Run `downsample_logging.py --resume`.
4. The same CSV file continues.  Its charge and energy columns continue
   from the last row before the reboot (6.4).


## GPIO wiring

Wire OUT0 to IN0 and OUT1 to IN1, and select 3.3 V I/O.

| Example | Expected |
| ------- | -------- |
| `gpio.py` | prints the counter 0, 1, 2, 3, 0, ... |
| `gpi_synchronized.py` | also wire OUT0 to IN+ and add a 1 kΩ load: finds edges and plots them |
| `trigger.py --start rising --end falling --display_trigger --display_stats --self_test` | one window per OUT0 period |
| `windowed_accum.py` | one CSV row per IN0 high window |
| `gpi_region.py --gpi 0 --vref 3v3` | one CSV row per IN0 high region |
| `trigger_host_pyjoulescope_driver.py` | with a load stepping above 1 A then below 0.1 A, TRIGGER OUT goes high then low, and starts low (6.14) |
| `timesync.py --out ts.csv` | with two or more instruments sharing one GPI0 signal, a header line, then one row per edge with offsets in microseconds (6.32) |


## Load

| Example | Setup | Expected |
| ------- | ----- | -------- |
| `fuse_js220.py` | a load above `--threshold2` for longer than `--duration` | prints `Fuse engaged!` and disconnects the load |
| `detector.py` | a load above 50 mA for 0.5 s | prints `detected 1` |
| `monitor.py` | a load stepping above 1 mA, then below for 2 s | starts then ends a capture, with voltage, not current, in the voltage columns (6.1) |
| `statistics_with_trigger_to_jls.py` | a load above 1 mA on a JS110 | records a JLS file (6.15) |
| `battery_discharge.py 3.0` | a battery or supply falling below 3.0 V | stops and disconnects the output |
| `low_voltage_shutoff.py -t 3.0` | a supply falling below 3.0 V | disconnects the output |
