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

# Example tests

These tests run each example the way a user does: as a subprocess, with
real arguments, then check what it printed, wrote and returned.  They never
import an example, so they keep passing when an example's internals change
and fail when its behavior changes.


## Running

Install the test dependencies:

    python -m pip install -U -r requirements.txt pytest

Run the offline tier, which needs no instrument:

    python -m pytest -m "not device"

Run everything, including the device tier against every connected
Joulescope:

    python -m pytest

A failing run prints the example's command line, exit code, stdout and
stderr.


## Tiers

| Tier | Needs | Marker | What |
| ---- | ----- | ------ | ---- |
| Offline | nothing | none | `--help`, argument errors, behavior with no instrument, and the JLS file examples on generated files. |
| Device | a Joulescope | `device` | Bounded runs, outputs and Ctrl-C, once per connected model. |
| Manual | a person | none | See [MANUAL.md](MANUAL.md). |

Offline tests hide every instrument from the example, even when one is
connected, so they also show the behavior with no instrument attached.
`shim/sitecustomize.py` does this by filtering the device list that
pyjoulescope_driver reports.  Device tests use the same mechanism so that an
example that uses every instrument only sees the one under test.


## Environment

| Variable | Meaning |
| -------- | ------- |
| `JOULESCOPE_EXAMPLES_BENCH` | The comma-separated device specifications of the instruments under test, such as `js320-31NB,js220-000415`.  Each must be connected, or its tests fail.  When unset, test every connected Joulescope. |
| `JOULESCOPE_EXAMPLES_EXCLUDE` | The device specifications to never test, such as an instrument that only supplies power to the bench. |

A device test that turns an output off, such as `dut_power.py off`, does so
on the instrument under test.  Exclude any instrument that powers something
which must stay on.


## Conventions

* Each test module covers one example, by its historical `bin/` name, and
  runs through every path in `harness.EXAMPLES` for that example.
* A known defect is a test of the correct behavior, marked
  `pytest.mark.xfail(strict=True, reason='6.N ...')` with its item number
  in doc/refactor_v1.md.  The commit that fixes it removes the mark.
* Model differences are part of the expected behavior.  A device test that
  only applies to some models checks the model and states why.
