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

# v1 refactor plan

This is the plan for a second attempt at the v1 refactor of the examples.
The first attempt, on the `feature/v1` branch in October 2026, was reverted.
It fixed real bugs, but it also changed behavior nobody had approved and made
the simplest examples harder to read.  This attempt is test-driven: no example
changes until tests pin down what it does today.

Items are numbered so they can be referred to as, for example, 4.3 or 9.1.2.

**Status, 2026 Oct 7.**  Sections 9 and 10 are implemented upstream in
joulescope 1.6.1 and pyjoulescope_driver 2.5.0.  Where the implementation
differs from this plan, the implementation wins; see the notes in those
sections.  The section 8 decisions are made; see the answers there.


## 1. Why the first attempt was reverted

Use these as the checklist of mistakes not to repeat.

1.1. **Uniform rules applied everywhere bloated the simple examples.**  The
style guide required every example to accept `--serial-number` and to copy a
device-selection block rather than call a helper.  `capture_simple.py` went
from 11 to 42 code lines, and `energy_printer.py` from 22 to 57.  Every
maintained example grew.

1.2. **Behavior changed without tests to catch it.**  Six regressions shipped
in the working tree, none of them intended:
  * 1.2.1. `scan.py` dropped the positional serial number, so
    `bin/scan_by_serial_number.py 000043` failed even through its `bin/`
    wrapper.
  * 1.2.2. `downsample_logging.py` exited when no instrument was attached,
    where it used to wait for one.  This broke boot-time start and the
    `--resume` after host reboot that its docstring advertises.
  * 1.2.3. `dut_power.py` rejected `ON`, `Enable` and `TRUE`: argparse
    `choices` ran before the old `.lower()`.
  * 1.2.4. `energy_printer.py` dropped `stop_fn`, so it no longer exited
    after an unplug.
  * 1.2.5. Moving callback work to the main thread lost the final output on
    exit in `downsample_logging.py` and `gpi_region.py`, because nothing
    emptied the queue.
  * 1.2.6. `read_by_callback.py` and `read_by_method.py` stopped logging by
    default.

1.3. **Deliberate changes were bundled with fixes.**  The Python 3.12 floor,
JLS v2 output from `capture_all.py`, the `jls_energy_plot.py` default display,
dropping JLS v1 from `jls_plot.py`, the `jls_export_points.py` header format,
and `fuse.py` disabling the fuse on exit were each reasonable on their own.
Mixed into a 10,000 line change, none got a real decision.

1.4. **Tests were written after the refactor and against its structure.**  The
regression suite introspected `get_parser()`, which only existed because of
the refactor.  It could not say whether the new code behaved like the old.

1.5. **Too much changed at once.**  A file move, a style pass, JS320 support,
bug fixes, new examples, CI and packaging all landed together, so no single
change could be reviewed or reverted on its own.


## 2. Ground rules

2.1. **Behavior is preserved by default.**  Command line, defaults, output
text, file formats, exit codes, and behavior with zero, one or several
instruments stay the same unless a numbered decision in section 8 says
otherwise.

2.2. **Tests come first and test behavior, not structure.**  Run each example
as a user would, as a subprocess with real arguments, and check what it
prints, writes and returns.  Never import its internals or rely on functions
the refactor will add.

2.3. **One example per pull request**, and within it, one commit per step of
section 4: tests, refactor, then each fix.  Mechanical moves (section 5.2)
are separate pull requests with no content changes.

2.4. **Simplicity budget.**  A refactor must not grow an example's code
(non-blank, non-comment lines) without a stated reason in the pull request.
Prefer a library helper, or a section 9 or 10 API change, to copying
boilerplate into examples.

2.5. **Rules have scope.**  A style rule names the examples it applies to.
Beginner examples (`capture_simple.py`, `capture_jls.py`, `statistics.py`,
`energy_printer.py`, `scan.py`) stay minimal and may skip options that the
advanced examples carry.

2.6. **Every user-visible change goes in the CHANGELOG**, under "Breaking
changes" when an old command line or output stops working.

2.7. **No change ships on a reviewer's word alone.**  A finding from a code
review, by a person or a model, becomes a failing test first.  If no test can
show the problem, it is not fixed in this effort.


## 3. Test infrastructure

Build this before touching any example.  The `ci/exampletest/` harness on
`feature/v1` (commit 865cd7b and later) is a usable starting point for the
runner, Ctrl-C handling and bench device selection, but its tests must be
rewritten to the black-box style of 2.2.

3.1. **Runner.**  Run an example by path in a subprocess with arguments, a
working directory and a timeout.  Capture stdout, stderr, the exit code and
any files written.  Stop streaming examples with Ctrl-C (`CTRL_C_EVENT` on
Windows, `SIGINT` elsewhere) and escalate to kill after a grace period.

3.2. **Tiers.**
  * 3.2.1. *Offline*: needs no instrument.  The command-line surface (3.3),
    `--help`, argument errors, behavior with no instrument attached, and the
    pyjls examples on generated JLS files.
  * 3.2.2. *Device*: runs on the bench against each supported model, the
    JS110, JS220 and JS320.  Bounded runs, outputs, and Ctrl-C.
  * 3.2.3. *Manual*: what the bench cannot automate yet, such as unplugging
    mid-run, rebooting the host, loopback wiring and tripping a fuse.  Keep a
    written checklist per example, and automate an item when the bench gains
    the hardware (for example a USB power switch).

3.3. **Command-line surface tests.**  For every example, record from `main`:
  * 3.3.1. every option and positional argument, including alternate
    spellings such as `--serial_number`;
  * 3.3.2. each option's default, shown by behavior rather than by reading
    the parser;
  * 3.3.3. accepted value forms, such as `10`, `1.5` and suffixed durations,
    and case handling;
  * 3.3.4. the exit code and message for a missing or invalid argument;
  * 3.3.5. what happens with no arguments at all.

3.4. **Output tests.**  Pin the stdout format, CSV headers and columns, and
JLS file contents (sources, signals, sample rate, length), using tolerances
for measured values.

3.5. **Instrument-count tests.**  Behavior with no instrument, one, and
several, including whether the example waits, exits, or picks one.

3.6. **Known-bug tests.**  Write each defect in section 6 as a test of the
correct behavior, marked `xfail` with a reference to the item number.  The
fix commit removes the mark.

3.7. **Line endings.**  Before the first commit, add `.gitattributes` with
`* text=auto`, and have the generators in `tools/` write native line endings
(the default `newline=None`).  Regenerate natively on Windows, not under WSL.

3.8. **Bench device selection.**  Keep a per-model device list and exclude any
device that only supplies power to the bench.  A model the configuration
lists but the bench lacks must fail, not skip.


## 4. Per-example procedure

For each example, in the order of section 5:

4.1. **Characterize.**  Write the tests of 3.3 to 3.5 for every parameter,
against the example as it is on `main`.

4.2. **Run them on `main`.**  They must pass.  A test that fails has found
either a test mistake, which you fix in the test, or a bug, which you add to
section 6 and mark `xfail` (3.6).  Do not change the example in this step.

4.3. **Commit the tests alone.**

4.4. **Refactor in small steps.**  Run the full test set for the example after
each step, and commit when it passes.  If a step fails, fix it or back it out;
never weaken a test to make a refactor pass.

4.5. **Fix bugs one at a time.**  Each fix removes one `xfail` mark and is its
own commit.

4.6. **Apply approved behavior changes** (section 8) one at a time.  Change
the test first so that it fails, then the example, then the CHANGELOG.

4.7. **Review the result.**  Compare against `main`: code line count (2.4),
whether the lesson is still the first thing a reader sees, and the 1.2
regression list.


## 5. Order of work

5.1. **Infrastructure** (section 3), plus tests for the infrastructure itself.

5.2. **The move from `bin/` to `examples/`.**  Move files without editing them,
add the `bin/` wrappers, and run every characterization test through both the
old and the new path.  The wrappers must forward argv, stdout, stderr and the
exit code unchanged, so that the tests pass identically through both.

5.3. **API changes upstream** (sections 9 and 10).  Release them before the
examples depend on them, so the examples can be simplified instead of
working around the packages.

5.4. **Examples, simplest first**, so the patterns settle on code that is easy
to review:
  * 5.4.1. pyjls examples, which need no instrument;
  * 5.4.2. beginner `joulescope` examples: `capture_simple.py`, `scan.py`,
    `statistics.py`, `capture_jls.py`, `energy_printer.py`;
  * 5.4.3. the remaining `joulescope` examples;
  * 5.4.4. `pyjoulescope_driver` examples, with `measure.py`, `read.py` and
    `dut_power.py` first and `downsample_logging.py` last.

5.5. **JS320 support** for each example, as its own pull request, after the
example has tests.

5.6. **New examples** (`hotplug.py`, `record.py`, `statistics.py` for the
driver), each with tests from the start.


## 6. Known defects on `main`

Found during the first attempt.  Re-verify each on `main` with a failing test
before fixing it.

6.1. `monitor.py` writes current into every voltage column.

6.2. `monitor.py` compares `'JS110'` against a lowercase device path, so a
JS110 runs at the wrong rate and statistics intervals are off by a factor of
two.

6.3. `monitor.py` allocates a 500 MB driver buffer and streams full-rate
samples it never reads, and writes files from the driver thread.

6.4. `downsample_logging.py --resume` restores charge and energy from the
current minimum and maximum columns.

6.5. `downsample_logging.py --duration` raises `AttributeError`.

6.6. `timesync.py` drops an edge on the first sample of a buffer, does not
track the previous level, and ignores `decimate_factor`.

6.7. `read_by_pyjoulescope_driver.py` fills dropped samples at absolute
sample ids rather than buffer offsets, and computes the returned `utc_range`
from an absolute sample id.  `read_by_callback.py` returns its zero-padded
buffer the same way.

6.8. `joulescope_examples/plot_cal.py` uses `BrokenBarHCollection`, removed
in Matplotlib 3.9, so `--plot` raises.

6.9. `statistics_logger.py` ignores `--file-fmt`, and prints forever with no
instrument.

6.10. `battery_discharge.py` releases a lock on every reading below the
threshold and raises on the second one.

6.11. `jls_plot.py` divides by zero on files shorter than 1000 samples.

6.12. `capture_all.py` returns 0 after an unsupported `--frequency`, waits
forever with no instrument, and leaks a device whose writer fails.

6.13. `measure.py` never closes the device, and hangs on a JS320 because its
model branch has no case for it.

6.14. `trigger_host_pyjoulescope_driver.py` ignores `--signal` and starts with
its output high.

6.15. `statistics_with_trigger_to_jls.py` raises `TypeError` when it triggers
without `--duration`, records the wrong source model on a JS220 or JS320, and
raises `KeyError` on a JS110.  It also writes files from the USB thread.

6.16. `dut_power.py` raises `IndexError` when given no argument.

6.17. `read_by_method.py` and `read_by_callback.py` only run from the
repository root.

6.18. `scan_by_serial_number.py` prompts on stdin whenever no serial number is
given, which blocks without a terminal.

6.19. `windowed_accum.py` imports `joulescope.stream_buffer.stats_to_api`,
which joulescope 1.6.0 no longer has.

6.20. `requirements.txt` omits `pyjoulescope_driver`, `pyjls`, `openpyxl` and
`psutil`.

6.21. Several examples can leave an instrument open on an error path, and some
callbacks call back into the driver from the driver thread (`fuse_js220.py`,
the trigger, detector, GPI region and timesync examples).

6.22. Nine examples branch on the device model and none recognizes the JS320.
This is missing support rather than a defect; handle it under 5.5.

Found during characterization (4.2) of the second attempt:

6.23. `jls_export_points.py` reports an exceeded `--duration` in time64
ticks labeled as seconds, such as `Duration exceeded: 5368709120.0 >
2147472910.0`.

6.24. `accumulators.py --source sensor` ignores `--duration`, and Ctrl-C
ends it with a `KeyboardInterrupt` traceback and without the final summary.

6.25. Some examples exit 0 after an error, because `__main__` calls `run()`
without `sys.exit()`: `battery_discharge.py` and `statistics_v1.py` with no
instrument, and `capture_jls_v1.py` after its usage message.

6.26. `capture_all.py --frequency 1000` records nothing: the JLS v1
`DataRecorder` raises "stream_buffer length too small" in the stream
callback, and the example still exits 0.

6.27. `read_by_method.py` and `read_by_callback.py` do not run from the
repository root either, since Python puts `bin/`, not the working
directory, on `sys.path`.  This extends 6.17: they only run with the
repository on `PYTHONPATH`.

6.28. `read_by_pyjoulescope_driver.py` waits forever for a signal that the
instrument does not have, such as `--signals T` on a JS110, and after it
skips every instrument as unsupported.

6.29. `timesync.py` raises on exit after it skips an unsupported instrument,
because it closes every device, including those it never opened.

6.30. On a JS220, `statistics.py`, `statistics_logger.py`,
`battery_discharge.py` and `statistics_v1.py` print at whatever statistics
rate the previous program left, such as 100 Hz after `measure.py`, instead
of 2 Hz.  They scan with `config='off'`, which does not configure the
instrument, and never set `reduction_frequency`.  See U.5.

6.31. `read_by_callback.py` returns up to 9,999 samples more than
`--duration` on a JS220 or JS320, such as 310,000 for 0.305 seconds.  It
rounds its buffer up to 10,000 samples and fills it, and these instruments
keep streaming briefly after the duration.  This is separate from 6.7, which
returned zeros after an early stop, such as on Ctrl-C.

6.32. `timesync.py --out` writes its CSV header without a newline, so the
header and the first row share a line.  Showing it needs two instruments
that share a GPI0 signal, so per 2.7 it waits for a bench with that wiring.
See tests/MANUAL.md.

6.33. `downsample_logging.py` exits when an instrument disappears while it
opens it, such as a JS320 that re-enumerates on a replug (see U.8).  The
open raises TimeoutError, and the logger stops with a FAIL event, although
it promises to survive unplug and temporary loss of USB communication.

Found by a review of the refactored examples:

6.34. `dut_power.py` exits 0 and prints nothing when no instrument matches,
such as for a `--device` typo, so the user believes it set the power.

6.35. `timesync.py` waits forever with no JS220 or JS320.

6.36. `statistics.py` waits forever with no instrument.

6.37. `record.py --signals` with an unknown name raises KeyError.

6.38. `statistics_with_trigger_to_jls.py` raises UnboundLocalError from its
`finally` block when the open fails, which hides the open error.

6.39. `trigger_out.py` and `gpi_region.py` wait forever when every instrument
is unsupported, such as with only a JS110.

The review also found that `downsample_logging.py` can leave a CSV file and
the instrument open when a publish fails after the open, and that the
examples handle Ctrl-C with two patterns, KeyboardInterrupt and a SIGINT
handler.  No test here shows the first, so per 2.7 it waits.

No black-box test can show 6.10 (`battery_discharge.py` releasing its lock
twice): the example stops after the first reading below the threshold, before
a second can arrive.  Per 2.7 it is not fixed on its own; the refactor
removes the lock.

Upstream defects that the examples expose.  Fix them upstream, not in the
examples; the example tests mark them `xfail` with these numbers.

U.1. joulescope 1.6.1 reports JS320 statistics `time.range` 8 times too
large: `Device._on_stats` assumes a 2 MHz sample counter.  `statistics.py`
prints `0.0, 4.0, 8.0` at 2 Hz on a JS320, and `0.0, 0.5, 1.0` on the JS110
and JS220.
Status 2026 Oct 8: fixed in pyjoulescope 038dfbb, on the
`fix/statistics_sample_freq` branch.  `Device._on_stats` assumed
`period = 1 / 2e6`, while the JS320 statistics report `time.sample_freq`
as 16 MHz.  It now uses `time.sample_freq`.  The six U.1 tests passed
strictly as XPASS with the fix, so they no longer carry the xfail mark.

U.2. pyjoulescope_driver 2.5.0 prints `in frame_id mismatch 0 != 1` to
stderr when it opens a JS320, now that the native log level defaults to
`error`.
Status 2026 Oct 8: fixed.  The message is now a WARNING, below the default
`error` level, and opening a JS320 prints nothing to stderr.

U.3. pyjoulescope_driver 2.5.0 prints `pkt_index skip: expected 0, received
8448` to stderr when a JS110 starts streaming, for example in
`current_ranging_filter.py`.
Status 2026 Oct 8: still open.  `current_ranging_filter.py` on a JS110
prints four `pkt_index skip` lines in each of 3 runs.

U.4. pyjoulescope_driver 2.5.0 intermittently crashes with an access
violation (0xC0000005) in `Driver.finalize()` after a JS110 streamed.
`python examples/pyjoulescope_driver/monitor.py -d <JS110 serial number>`,
then Ctrl-C after 2 seconds, crashes in 7 of 20 runs on Windows, as it
exits its `with Driver()` block.  measure.py on a JS110 crashed once in
about 40 runs, and a minimal script with the same topics did not crash in
40 runs.  The JS220 and JS320 did not crash.
Status 2026 Oct 8: still open, although pyjoulescope_driver 2.5.0 fixed a
use-after-free in `Driver.finalize()` after a JS110 streamed.  The same
command crashed in 5 of 20 runs through the test shim and 12 of 20 runs
without it.  faulthandler places the crash in `Driver.finalize()`.  It did
not occur in the full suite run.
Root cause, 2026 Oct 8: the WinUSB backend's `device_close()` freed the
WinUSB handle while a control transfer, such as a JS110 status poll, was
in flight.  Freeing the handle aborted the transfer, and the device
thread's `ctrl_complete()` then called `WinUsb_GetOverlappedResult()`
with `INVALID_HANDLE_VALUE`.  cdb caught it there, while the main thread
was in `Driver.close()`.  A Ctrl-C that lands while `monitor.py` opens
the instrument leaves the `with Driver()` block, so finalize closes a
JS110 that is still streaming.  A SIGINT raised inside the process
crashed it too, so the console is not involved.  The libusb backend
cancels every transfer on close, so it is not affected.
Status: fixed in joulescope_driver 5e2fb08, on the
`fix/winusb_close_ctrl` branch.  `device_close()` now cancels and waits
for the transfer in flight, and answers each queued control transfer
with `JSDRV_ERROR_CLOSED`.  A sweep of Ctrl-C times from 0.6 to 3.0
seconds crashed in 15 of 33 runs before the fix and 0 of 33 after, and
60 more runs at 2 seconds did not crash.

U.5. joulescope 1.6.1 `scan(config='off')` keeps the statistics rate that the
instrument already has on a JS220, but sets 2 Hz on a JS320.  The models
should agree.
Status 2026 Oct 8: fixed by the pyjoulescope_driver 2.5.0 JS220 `defaults`
open, which now restores the default settings.  After another program set
100 Hz, both models report 2 Hz.  On the JS220, the first statistics value
still has the old 0.01 second delta, in 3 of 3 runs.  The examples still
set `reduction_frequency` themselves (6.30), which keeps them explicit.

U.6. joulescope 1.6.1 `JlsWriter` records past `device.start(duration=...)`:
for 1 second, 2,000,000 samples on a JS110 but 1,000,944 on a JS220 and
1,027,296 on a JS320.  It writes the whole stream buffer update in which the
duration ends.
Status 2026 Oct 8: still open.  A 1 second `capture_jls.py` records
2,000,000 samples on the JS110, 1,000,440 to 1,001,196 on the JS220 and
1,027,296 on the JS320.

U.7. pyjoulescope_driver 2.5.0 has no public table of the signals and their
topics, so `read.py` imports the private `record._SIGNALS` and
`record._signal_name_map`.
Status 2026 Oct 8: still open.

U.8. A JS320 (firmware 1.1.10) sometimes drops off USB when a program reopens
it about 2 seconds after closing it, so the open times out.  Seen in 2 of
11 runs of the downsample_logging.py hotplug test.  WinUSB reports "A device
which does not exist was specified" during the open.
Status 2026 Oct 8: still open with JS320 firmware 1.1.11.  The hotplug
sequence logged OPEN FAILED, with the same WinUSB error, in 2 of 8 runs.
`downsample_logging.py` recovers (6.33).  Opening the JS320 every 2 seconds
from a new process, with no stream in between, succeeded about 60 times.
Investigation, 2026 Oct 8: a race between the reopen and Windows USB
selective suspend.  The JS320 registry entry has `DeviceIdleEnabled` 1
and `DefaultIdleTimeout` 2000 ms, from the MS OS 2.0 descriptors that
firmware 1.1.4 added; the JS110 and JS220 have idle disabled.
* Only a reopen 2 seconds after the close fails.  The hotplug test
  failed in 11 of 36 runs with a 2.0 second gap, but in 0 of 12 with
  1.5 seconds and 0 of 12 with 3.0 seconds.
* The time from `device_open` to `ll_bulk_open` in the driver log, which
  covers CreateFile and WinUsb_Initialize, shows the device state.  It
  takes 0 to 1 ms when the JS320 is awake (1.5 s gap) and 32 to 35 ms
  when it is suspended and resumes (3.0 s gap).  At 2.0 seconds, every
  passing reopen took 32 to 35 ms and every failing reopen 22 to 25 ms:
  the open arrived while the suspend was in progress.
* The first bulk OUT transfer of the link request then fails with
  ERROR_OPERATION_ABORTED (995) or ERROR_NO_SUCH_DEVICE (433).  Windows
  logs Kernel-PnP event 1010, "Device USB\VID_16D0&PID_135A\31NB has
  been surprise removed as it is reported as missing on the bus", and
  the JS320 re-enumerates about 220 ms later.
* The JS320 does not reboot: its boot history (`minibitty info
  --verbose`) has no new entries after about 10 failures.  The firmware
  only soft-disconnects at USB initialization, so the hub, not the
  firmware, removed the device, as after a failed resume.
* The driver sends the same topics in the example and in standalone
  scripts, which did not fail in about 160 reopens.  Those reopens
  arrived when the device was already suspended or still awake.
Next steps: find why the JS320 fails a resume that follows the start of
a suspend, which needs the firmware log or a USB analyzer, with the
hotplug test as the reproduction.  The device runs firmware 1.1.11, but
the local js320 checkout ends at 1.1.8.  minibitty does not implement
the RM0477 erratic-error soft-disconnect recovery (ESUSP), which may be
related.  Disabling selective suspend, or a longer idle timeout, would
avoid or move the race, at a power cost.
Root cause, 2026 Oct 9, on a JS320 (8W2A, firmware 1.1.11) with a J-Link
polling the STM32H7S3 USB OTG HS registers (DSTS, DCFG) at about 1,800
samples per second during the hotplug test, with no firmware changes.
The test failed in 11 of 60 runs.
* After the close, the JS320 stays awake.  About 2.003 s after the close,
  the reopen and Windows' 2 s selective-suspend timer coincide: the host
  stops SOFs, then drives the resume K for about 21 ms.  In 14 runs the
  open came first and no suspend occurred.
* The JS320 never reaches suspend (DSTS.SUSPSTS stays 0) in any run.
* All 10 failures in the second set of 40 runs, and the one failure in
  the first 20, have the resume K start within about 0.6 ms of the last
  SOF.  Passing runs with a suspend had the K start 0.55 to 9.3 ms after
  the last SOF.
* In every failure, the USB core raises a USB reset 20.7 to 21.6 ms
  after the K starts, at the end of the resume: the firmware's USBRST
  handler clears DCFG.DAD to 0, and DSTS.ENUMSPD reports full speed.
  The line shows no 10 ms SE0 and no high-speed chirp, so the host did
  not reset the port.  The host then sends to the old address at high
  speed, the first bulk transfer fails, the core suspends, and about
  100 ms later Windows resets the port, removes the device ("missing on
  the bus") and enumerates it again at high speed.
* The firmware did not reboot: the boot history only gained the
  HARDWARE_RESET entries from the J-Link connects.
* The firmware's suspend and resume handling plays no part: the core
  reports a reset, and the firmware handles it as a reset.  The lost
  event handling in usbd_isr_handler and the missing erratic-error
  recovery are separate.
So the trigger is a selective suspend that Windows cancels within about
0.6 ms, and the cause is the STM32H7S OTG HS core treating the end of a
resume that arrives before its 3 ms suspend detection as a bus reset,
without the high-speed handshake.  No published erratum was found.  A
USB protocol analyzer would confirm that the host signaling is legal.
Correction and root cause, 2026 Oct 9, with a Beagle USB 5000 v2 on the
JS320 link and a JS320 firmware build with trace logging
(`config.trace.log: true`, no code changes), on Windows with an Intel
xHCI.  The J-Link estimate above, a resume within about 0.6 ms of the
last SOF, was an artifact of its sampling rate.
* The failure does not need a hub.  With the JS320 on a Genesys hub
  (05E3:0610) it failed in 2 of 34 runs, and on an xHCI root port in 3
  of 40 and 5 of 40 runs.  The hub drives a 20 ms resume, and the root
  port a 50 ms resume.
* Windows suspends the port when its 2 s idle timer expires (behind the
  hub, with SET_PORT_FEATURE(PORT_SUSPEND)), and the reopen immediately
  resumes it.  The failure depends only on when the resume K starts
  after the last SOF: 3.13 to 3.51 ms in all 10 failures, and 3.62 ms or
  later in all 30 passing runs that suspended.
* That interval is the USB 2.0 reset and suspend detection window.
  After 3.0 to 3.125 ms of idle, a high-speed device reverts to full
  speed and samples the line 100 to 875 us later: SE0 means reset, J
  means suspend.
* The JS320 USB core reports nothing for a resume that starts in that
  window: no WKUPINT and no USBSUSP.  It stays in full-speed mode through
  the resume.  When the resume ends, the host's high-speed terminations
  make the line read SE0 to a full-speed device, so the core raises
  USBRST and drives the high-speed chirp K for 2 ms.  The host does not
  answer, because it did not reset the port, so the core enumerates at
  full speed (ENUMDNE) and then suspends.  The Beagle shows the chirp K
  and the full-speed J, and the trace shows USBD reset, USBD enum and
  USBD suspend, 51, 56 and 61 ms after the resume starts.
* A resume that starts after the window works: from about 3.6 ms the
  core raises WKUPINT (was_suspended 0), and after about 6 ms USBSUSP and
  WKUPINT (was_suspended 1), and the device returns to high speed.
* ES0596 lists no OTG_HS erratum for this.  The firmware cannot restore
  high speed by itself, because only a host reset starts the chirp
  handshake; it can detect the condition (USBRST with no preceding
  WKUPINT, then ENUMDNE at full speed after a high-speed session) and,
  for example, soft-disconnect so that Windows enumerates it again
  sooner.  The open that hit the window still fails.

U.9. A JS320 (firmware 1.1.11) sometimes stops answering the sensor state
request after a program that is streaming from it exits without closing
it.  Every later `defaults` open times out after 1 second: the driver logs
`state_fetch: GET_INIT BUSY for 's'` for each of 20 retries, then
`GET_INIT failed status=19`.  Opens with a longer timeout, or in `restore`
mode, succeed at first, but later failed in `restore` mode as well.
Publishing `s/sys/!reset` recovered it for a single open only, and
`c/sys/!reset` (value 0) recovered it fully.  A hard kill of
`record.py` after 3 seconds of streaming caused this in 1 of 8 runs.
Three runs that crashed while writing a JLS file to `NUL` also left it in
this state.  The same kill did not affect the JS110 or JS220.  The example
tests close every instrument, so they do not show it, but an instrument
left in this state fails the next test that opens it.


## 7. Regression checklist

Run through this list in step 4.7 for every example.

7.1. Do old command lines still work, positional arguments and alternate
spellings included, through both the new path and the `bin/` wrapper?

7.2. Is argument case handled as before?

7.3. Does the example still start with no instrument attached, if it used to?

7.4. Does it still exit, or keep running, when an instrument is unplugged, as
before?

7.5. Is the last output written on Ctrl-C and on `--duration` expiry?  Anything
handed to the main thread through a queue must be emptied before close.

7.6. Are logging defaults unchanged?

7.7. Are output formats unchanged: stdout, CSV headers, file formats and file
names?

7.8. Did the code line count grow, and if so, why?


## 8. Decisions needed before changing behavior

Each needs an explicit yes or no from the maintainer.  Until then, keep the
`main` behavior.  The maintainer answered each on 2026 Oct 7.

8.1. **Minimum Python 3.12.**  This follows from `joulescope>=1.6.0`, and
drops Ubuntu 22.04, Debian 12, RHEL 9 and the macOS system Python.
*Decision: yes.  joulescope 1.6.1 already requires Python 3.12.*

8.2. **`capture_all.py` writes JLS v2** instead of JLS v1 under the same file
name.
*Decision: yes, JLS v2 with `JlsWriter`.*

8.3. **Plot defaults.**  Should plotting examples display only with `--show`?
On `main`, `jls_energy_plot.py` displays by default.  If the default changes,
exit non-zero when there is nothing to do.
*Decision: both plotting examples show the plot unless `--out` is given,
or when `--show` is given, which is the `main` behavior of
`jls_energy_plot.py`.*

8.4. **`jls_plot.py` and JLS v1.**  Drop v1 reading only if something else
can plot a v1 file.
*Decision: keep v1 reading.*

8.5. **`jls_export_points.py` header.**  The `# ` prefix works with
`np.loadtxt`; a plain header works with pandas.  Keep the prefix, or add an
option.
*Decision: keep the `# ` prefix.*

8.6. **`fuse.py` on exit.**  Disable the fuse, or leave it armed so the
instrument stays protected after the script ends?
*Decision: leave it armed, and say so on exit.*

8.7. **`--serial-number` everywhere.**  Only where it earns its place, or
only through a library helper (9.1)?
*Decision: follow the pyjoulescope_driver 2.5.0 entry points instead.  Add
`--device`, which takes a device specification such as `js320`, `31NB` or
`js320-31NB`, only to examples that already select a device or use several.
Keep `--serial-number` and `--serial_number` as hidden aliases where they
existed.  Add the `-d` short form only where `-d` is not already taken, such
as by `--duration`.  Beginner examples (2.5) do not get it.*

8.8. **`scan.py` with no arguments.**  List the devices, rather than prompting
on stdin?
*Decision: yes; this also fixes 6.18.*

8.9. **Bool topics.**  Publish `'on'`/`'off'` instead of `1`/`0`.  This needs
pyjoulescope_driver 2.4.2 or later, and some topics differ by model; see
10.4.
*Decision: no.  Keep `1`/`0`, which the pyjoulescope_driver 2.5.0 getting
started guide uses and every model accepts.*

8.10. **Hyphenated options** with the underscore spelling kept as an alias.
*Decision: yes.*


## 9. Recommended changes to `joulescope`

Each one removes code that every example would otherwise copy.

9.1. **Select by serial number.**
  * 9.1.1. Add `serial_number=None` to `scan()` and `scan_require_one()`,
    matched exactly and case-insensitively.
  * 9.1.2. Have `scan_require_one()` name the devices it found in its error,
    and say how to pick one.
  * 9.1.3. Raise a specific exception class rather than `RuntimeError`, so
    an example can catch "no device" without catching everything.

  With these, every single-device example selects its instrument in one line:
  `device = scan_require_one(config='auto', serial_number=args.serial_number)`.

9.2. **Statistics source.**  `statistics_callback_register(cbk, source)`
ignores `source`; the actual source depends on the model and on
`scan(config=...)`.  Deprecate `source` with a warning on first use and
document which source each model and config uses.

9.3. **Deprecate `Device.status()`.**  The v1 device returns a constant dict,
so examples that poll it teach nothing.  Warn on first use.

9.4. **Statistics on the caller's thread.**  Statistics callbacks,
`stream_notify` and `stop_fn` all run on the USB thread, so every example
builds its own queue.  Add two blocking methods:
9.4.1. `Device.statistics_get(timeout)` - get next statistics value
9.4.2. `Device.statistics_iter(count, timeout)` - iterate over all statistics values
  If count is not provided, iterate "forever"
  If timeout is not provided, used 2 seconds.

9.5. **`JlsWriter` that can open anywhere.**  `JlsWriter.open()` calls
`device.info()` and `parameter_get()`, so it cannot be opened from a callback,
which forced one example to reimplement the writer.  Read the device info at
construction, or accept it as an argument.

9.6. **Public helpers.**  Make `_signals_validator` and
`_sampling_rate_validator` public, or give `Device.sampling_frequency` and
`JlsWriter` everything the examples need from them.

9.7. **Run length.**  Document the difference between `device.start(duration)`
with `stop_fn` and a wall-clock loop, and recommend one; the examples
currently use three different patterns.


**As implemented in joulescope 1.6.1:**
  * 9.1: `scan()`, `scan_require_one()` and `scan_for_changes()` take device
    specifications as their first argument, the same as pyjoulescope_driver
    `Driver.device_paths()`, rather than a `serial_number` keyword.  They
    only return Joulescope instruments.  `scan_require_one()` raises
    `ScanError`, both a `ValueError` and a `RuntimeError`, whose message
    lists the available devices.  A single-device example selects its
    instrument with `scan_require_one(args.device, config='auto')`.
  * 9.2: the `source` argument is deprecated with a warning.  Added
    `Device.statistics_source` and the statistics `source` key.
  * 9.3: `Device.status()` is deprecated with a warning.
  * 9.4: `Device.statistics_get(timeout)` and
    `Device.statistics_iter(count, timeout)`, as planned.  The buffer holds
    the 100 most recent values.
  * 9.5: `JlsWriter` accepts `info` and `sampling_frequency`, and reads an
    open device at construction, so `open()` works from a callback.
  * 9.6: `signals_validator()` and `sampling_rate_validator()` are public.
  * 9.7: the streaming documentation recommends
    `device.start(stop_fn=..., duration=...)` with a `threading.Event`.

## 10. Recommended changes to `pyjoulescope_driver`

10.1. **Release the device filter.**  `pyjoulescope_driver/device_filter.py`
already provides `device_filter(device_paths, specs)` and `device_match()`,
which handle full paths, `model/serial`, a model, or a serial number, and
ignore non-Joulescopes such as a MiniBitty.  Release it and export it from
the package, so examples replace their hand-written filters with one call.

10.2. **Require one device.**  Add `require_one(device_paths, spec=None)`, or
`Driver.device_paths(filter=...)`, that returns one path or raises a clear
error naming the devices found and how to choose one.


10.3. **Clean up what was opened.**  Have `Driver.__exit__` close every device
it opened, ignoring errors from devices that have since disappeared, and
document that.  Examples could then drop the `opened = []` bookkeeping and the
per-device `try/except` around the stop publishes.

10.4. **One value type per topic across models.**  `c/trigger/dir` is a u8 with
the options `input`/`output` on the JS220 but a bool on the JS320, so no
single value works on both.  Make the driver accept either form on both
models, or align the firmware metadata.  Audit the other topics shared by the
JS220 and JS320 for the same problem.

10.5. **Surface configuration errors.**  `publish(..., timeout=0)` cannot
report `PARAMETER_INVALID`.  Document when to use a blocking publish, or
report deferred errors through a log or callback.

10.6. **Model capabilities.**  Expose capabilities, such as "has a fuse", "host
or sensor statistics" and "native sample rate", so examples ask the device
rather than branching on the model name.  Keep the visible model branch only
where the difference is the lesson.

10.7. **Callback threading guide.**  State in the package documentation which
calls are allowed from a callback, and provide the hand-off helper the
examples keep writing: a subscription that delivers to a `queue.Queue`.

10.8. **A simulated device.**  If the driver does not already have one, add a
virtual Joulescope that streams synthetic samples and statistics.  It would
let the device-tier tests (3.2.2) run in CI without hardware.

10.9. **Keep the entry points and examples from drifting.**  The `statistics`
entry point does not filter by model and publishes `1` to `s/stats/ctrl`.  Fix
it, and have examples that mirror an entry point (`record`, `statistics`)
either call the shared code or point to the entry point instead of copying
it.


**As implemented in pyjoulescope_driver 2.5.0:**
  * 10.1 and 10.2: `Driver.device_paths(specs, brand)`, its alias
    `Driver.find_devices()`, and `Driver.find_one_device(specs, brand)`,
    which raises `device_filter.DeviceFilterError`, a `ValueError` that
    names the available devices.  Paths are `DevicePath` instances, a `str`
    subclass with `model`, `serial_number` and `brand`.  The
    `device_filter` module is a namespace with `find()` and `find_one()`.
    Pass `brand='joulescope'` to ignore a MiniBitty.
  * 10.3: `Driver.finalize()`, including exiting `with Driver() as d:`,
    closes each device that it opened and that is still connected.
    `with d.open(path) as device:` returns a `DeviceContext`, which takes
    topics relative to the device and unsubscribes on close.
    `Driver.subscribe()` returns a `SubscribeContext`.
  * 10.4: not changed.  `c/trigger/dir` is still a u8 on the JS220 and a
    bool on the JS320, but publishing `1` works on both.
  * 10.5: an error from a `timeout=0` publish now logs at ERROR level to the
    `jsdrv` logger, and the native log level defaults to `error`.  The JS320
    confirms every publish.
  * 10.6: no capabilities API.  doc/getting_started.md has a table of model
    differences instead.
  * 10.7: doc/getting_started.md states the callback rules.  There is no
    queue helper, but `Driver.device_watch(on_add, on_remove, specs, brand)`
    reports device additions and removals without races.
  * 10.8: no simulated device.
  * 10.9: the entry points select devices with `--device`/`-d` and
    `--brand`, and the Joulescope entry points only match Joulescopes.

## 11. Done

The effort is done when:

11.1. every example on `main` has characterization tests that pass on both
`main` and the refactored code, except tests changed by an approved section 8
decision;

11.2. every section 6 defect is fixed, or still marked `xfail` with a reason;

11.3. no example fails the section 7 checklist;

11.4. no beginner example (2.5) has more code than on `main`;

11.5. the CHANGELOG lists every user-visible change, with breaking changes
under their own heading.


## 12. Status of the second attempt

As of 2026 Oct 7, on the `feature/v1` branch, against the local joulescope
1.6.1 and pyjoulescope_driver 2.5.0, on Windows with a JS110, JS220 and
JS320:

12.1. Done: the infrastructure (5.1), characterization tests for every
example (4.1 to 4.3), the move to examples/ with bin/ wrappers (5.2), the
pyjls, beginner, joulescope and pyjoulescope_driver examples (5.4), JS320
support (5.5), and hotplug.py, record.py and the driver statistics.py
(5.6).  Each step is its own commit.

12.2. Fixed, each with a test that failed first: 6.1, 6.2 (by the 6.3
refactor), 6.4, 6.5, 6.7 for read_by_callback.py, 6.8, 6.9, 6.11 to 6.20,
6.22 to 6.31 and 6.33 to 6.39.  6.10 is gone with the lock that caused it.

12.3. Not fixed, since no test on this bench can show them (2.7): 6.3's
file writes on the driver thread in monitor.py, 6.6 (needs GPI wiring),
6.7 for read.py (needs dropped samples), 6.21 except fuse.py, which now
publishes with timeout=0, and 6.32 (needs two instruments sharing GPI0).
tests/MANUAL.md covers the wiring and load cases.

12.4. The upstream defects U.1 to U.8 remained as of 2026 Oct 7.  The
tests mark U.1 as `xfail` on the JS320.  U.4 can still crash a JS110 test
intermittently.  See 12.6 for the 2026 Oct 8 rebaseline.

12.5. The section 11 criteria: 11.2, 11.4 and 11.5 hold.  For 11.1, the
characterization tests ran on `main` code before each change; where an
approved decision or a fix changed behavior, the test changed first, in
the same commit as the example.  For 11.3, the regression checklist holds
for every example, except that a few error messages now come from the
libraries, such as `No Joulescope found` (decision 8.7).

12.6. Rebaseline, 2026 Oct 8, against the local pyjoulescope_driver 2.5.0
(joulescope_driver c19dde7, built after that commit), joulescope 1.6.1
(pyjoulescope 1f6653a), JS220 firmware 1.3.0 with FPGA 1.3.3, and JS320
firmware and FPGA 1.1.11:

* The full suite passed, with no example changes: 1166 passed, 55
  skipped and 6 xfailed (U.1), in 34 minutes.  U.4 did not occur in this
  run.
* Fixed upstream: U.2 and U.5.
* Fixed afterwards: U.1 in pyjoulescope and U.4 in joulescope_driver,
  each on its own branch.  With both, the full suite passed: 1172 passed
  and 55 skipped, in 33 minutes.
* Still open: U.3, U.6, U.7 and U.8.  Each entry in section 6
  has the evidence.
* New: U.9, a JS320 that stops answering after a streaming program exits
  without closing it.
* The JS220 `defaults` open now restores the default settings instead of
  keeping the previous program's settings.  No example relied on the old
  behavior: dut_power.py, which must keep the instrument's state, already
  opens with `mode='restore'`.
