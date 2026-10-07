<!--
# Copyright 2019-2025 Jetperch LLC
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


# CHANGELOG

This file contains the list of changes made to pyjoulescope_examples.


## 1.0.0

2026 Oct [in progress]

Breaking changes:

* Requires Python 3.12 or newer, joulescope 1.6.1 or newer and
  pyjoulescope_driver 2.5.0 or newer.
* capture_all.py records JLS v2 files instead of JLS v1, with the same
  file names.  Read them with pyjls, or plot them with
  examples/pyjls/jls_plot.py.  This also records at low `--frequency`
  values, such as 1000, which recorded nothing before.
* The pyjoulescope_driver examples select an instrument with `--device`
  (`-d` where free), the same as the pyjoulescope_driver 2.5.0 entry points.
  It takes a device specification: a serial number, a model, such as
  js220, or both, such as js220-000415.  `--serial-number` and
  `--serial_number` still work.  The messages for no matching device or
  several now come from pyjoulescope_driver, such as
  `No Joulescope found`.  Changed in measure.py, dut_power.py, detector.py,
  gpi_region.py, timesync.py, trigger_out.py (was
  trigger_host_pyjoulescope_driver.py),
  fuse.py (was fuse_js220.py) and read.py (was
  read_by_pyjoulescope_driver.py), which has no `-d`, since `-d` is
  `--duration`.
* dut_power.py parses its arguments with argparse.  A missing or invalid
  state exits 2 with the argparse message, instead of printing the usage.
  It only controls Joulescope instruments, not other USB devices that the
  driver lists, such as a MiniBitty.
* scan.py (was scan_by_serial_number.py) lists the connected Joulescopes
  when given no argument, instead of prompting on stdin.  Its argument is
  now a device specification: a serial number as before, matched without
  regard to case, or a model, such as js220, or both, such as js220-000415.
  An unknown device prints the available devices and exits 1, instead of
  raising KeyError.

Fixes:

* monitor.py: write voltage in the voltage columns (was current), and exit
  1 when no Joulescope is connected (was 0).
* timesync.py: exit cleanly after skipping an unsupported instrument (was
  RuntimeError on exit).
* trigger_out.py (was trigger_host_pyjoulescope_driver.py): detect on the
  `--signal` given, which is now one of i, v or p.  It always used i.  It
  also starts with the trigger output low, which it set high.
* fuse.py (was fuse_js220.py): exit 1 when no Joulescope is connected (was
  0), and explain that the JS110 has no fuse (was RuntimeError).
* dut_power.py: exit 1 after the usage message when given no argument
  (was IndexError).
* read.py: exit 1 with the error when the instrument does not have a
  requested signal, such as `--signals T` on a JS110.  It waited forever.
* statistics_v1.py and capture_jls_v1.py: exit 1 after an error (was 0).
* windowed_accum.py: runs with joulescope 1.6 (was ImportError for
  stats_to_api).
* statistics_with_trigger_to_jls.py: record the instrument model in the
  JLS file (was JS110 on every model), record on a JS110 (was KeyError),
  and record 120 seconds without `--duration` (was TypeError).
* statistics_logger.py: format file rows with `--file-fmt` (was ignored),
  and exit 1 when no Joulescope is connected (printed rows forever).
* read_by_method.py and read_by_callback.py: run from any directory.
  They previously needed the repository on PYTHONPATH.
* read_by_callback.py: return exactly `--duration` of samples, which was up
  to 9,999 more on the JS220 and JS320, and after Ctrl-C, return only the
  samples received, which was the whole buffer, padded with zeros.
* read_by_method.py and read_by_callback.py: `--plot` works with
  Matplotlib 3.9 and newer (was AttributeError: BrokenBarHCollection).
* jls_plot.py: plot JLS v2 files shorter than 1000 samples (was
  ZeroDivisionError).
* jls_export_points.py: report an exceeded `--duration` in seconds (was
  time64 ticks).
* statistics.py, battery_discharge.py and statistics_logger.py: display
  statistics at 2 Hz on a JS220, rather than at the rate that a previous
  program left.
* battery_discharge.py: exit 1 when no Joulescope is connected (was 0).
* capture_all.py: exit 1 when no Joulescope is connected (waited forever),
  and after an unsupported `--frequency` (was 0).
* accumulators.py --source sensor: stop after `--duration` (was ignored),
  and print the final summary on Ctrl-C (was a KeyboardInterrupt
  traceback).

Other changes:

* fuse.py says on exit that the fuse remains enabled, which it always did.
* Added JS320 support: measure.py, read.py, detector.py, gpi_region.py,
  timesync.py and
  trigger_out.py.
* capture_jls.py (was capture_jls_v2.py) records at least `--duration`
  of samples, counted by the instrument, and exits when the instrument
  stops, such as when unplugged.  It previously used a wall-clock timer,
  so a 1 second capture could record 0.9 seconds.
* Removed calls to the deprecated joulescope Device.status() and the
  statistics callback source argument, which now print
  DeprecationWarning: statistics.py, accumulators.py,
  battery_discharge.py, statistics_logger.py,
  statistics_with_trigger_to_jls.py and the legacy examples.
* jls_plot.py shows the plot unless given `--out`, the same as
  jls_energy_plot.py.  It previously did nothing without `--out` or
  `--show`.
* Options use hyphens, such as `--sample-count`.  The underscore spelling,
  such as `--sample_count`, still works.  Changed in jls_plot.py,
  jls_energy_plot.py and statistics_logger.py.
* requirements.txt now installs every package that the examples import:
  pyjoulescope_driver, pyjls, openpyxl, psutil and, on Windows, pywin32.
* Moved the examples from bin/ into examples/, grouped by package:
  joulescope, pyjoulescope_driver, pyjls and legacy.  Some examples have
  new names, such as scan.py for scan_by_serial_number.py.  The bin/
  scripts still work by their old names and run the moved examples.
  See tools/gen_bin_wrappers.py.
* Added tests that run every example as a user does, with no instrument,
  each instrument and several instruments.  See tests/README.md.


## 0.14.1

2025 Feb 4

* Fixed read_by_callback.py  #17


## 0.14.0

2025 Jan 2

* Added bin/fuse_js220.py.
* Added bin/timesync.py
* Updated capture.py to use pyjoulescope_driver record entry point.


## 0.13.0

2024 Jun 14

* Added bin/measure.py.


## 0.12.0

2024 Jun 11

* Added bin/gpi_region.py.


## 0.11.0

2024 Mar 6

* Updated downsample_logging to directly use pyjoulescope_driver.
  * Always use sensor-side statistics
  * Removed JLS recording support
  * Improved device remove / add robustness


## 0.10.1

2024 Feb 27

* Added bin/jls_export_points.py example.
* Added bin/statistics_v1.py example


## 0.10.0

2024 Jan 22

* Added detector example which uses pyjoulescope_driver directly.


## 0.9.10

2023 Dec 12

* Updated bin/read_by_callback.py to handled JS220's sample index offsets.


## 0.9.9

2023 Mar 24

* Added monitor example.


## 0.9.8

2021 Oct 6

*   Created statistics_logging.py example.


## 0.9.7

2021 Aug 18

*   Updated capture_jls_v2 to use new joulescope.jls_writer module. 
*   Bumped joulescope dependency to 0.9.7.
*   Added JLS v2 support to trigger.py.


## 0.9.6

2021 Aug 17

*   Renamed example "capture_jls.py" to "capture_jls_v1.py"
*   Added "capture_jls_v2.py" example.


## 0.9.5

2021 Jun 17

*   Fixed "trigger.py" example.
    *    Ignore missing samples.
    *    Fixed IN1 support.


## 0.9.4

2021 Mar 8

*   Added "trigger.py" example.


## 0.9.3

2021 Feb 25

*   Added "windowed_accum.py" example.


## 0.9.2

2020 Dec 16

*   Added "capture_all.py" example.


## 0.9.1

2020 Sep 15

*   Added "scan_by_serial_number.py" example.


## 0.9.0

2020 Sep 3

*   Added statistics example that displays on-instrument statistics from all
    connected Joulescopes.
*   Added energy printer from sensor.
    *   Added new example that uses sensor-side statistics.
    *   Renamed energy_printer.py to energy_printer_host.py.
*   Reduced memory footprint for downsample_logging.


## 0.8.7

2020 Jul 8

*   Improved bin/downsample_logging.py:
    *   Added JLS logging option.
    *   Added summary information print at end.


## 0.8.6

2020 Feb 26

*   Fixed examples to work with joulescope 0.8.6.
