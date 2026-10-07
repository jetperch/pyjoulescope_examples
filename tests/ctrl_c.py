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

"""Send Ctrl-C to a Windows process that has its own console.

usage: python ctrl_c.py {pid}

Windows can only send CTRL_C_EVENT to every process attached to a console,
so the test runner starts each example with its own hidden console.  This
helper runs as a separate process, attaches to that console, ignores the
event itself, and sends it.  The example then receives a real Ctrl-C, the
same as when a user presses it.
"""

import ctypes
import sys
import time


def run(pid):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(pid):
        return ctypes.get_last_error() or 1
    kernel32.SetConsoleCtrlHandler(None, True)  # do not stop this process
    if not kernel32.GenerateConsoleCtrlEvent(0, 0):  # CTRL_C_EVENT, this console
        return ctypes.get_last_error() or 1
    time.sleep(0.1)  # stay attached until the console delivers the event
    kernel32.FreeConsole()
    return 0


if __name__ == '__main__':
    sys.exit(run(int(sys.argv[1])))
