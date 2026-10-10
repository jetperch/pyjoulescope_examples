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

"""A matplotlib backend that renders like Agg and reports plt.show().

The tests select it with MPLBACKEND=module://mpl_show_probe, so that
plt.show() never opens a window, and prints SHOWN to stderr instead,
followed by each line of figure-level text, prefixed by TEXT.
Plain Agg warns on show(), but not on Linux without DISPLAY, so it cannot
tell the tests whether an example showed a plot.
"""

import sys
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg

SHOWN = 'mpl_show_probe: plt.show() called'
TEXT = 'mpl_show_probe text: '


class FigureManager(FigureManagerBase):

    def show(self):
        sys.stderr.write(SHOWN + '\n')
        for text in self.canvas.figure.texts:  # figure-level text, such as a statistics box
            for line in text.get_text().splitlines():
                sys.stderr.write(f'{TEXT}{line}\n')
        sys.stderr.flush()


class FigureCanvas(FigureCanvasAgg):
    manager_class = FigureManager
