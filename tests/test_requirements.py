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

"""Check that requirements.txt installs everything the examples import."""

import ast
import harness
import os
import pytest
import re
import sys


# Import name to the distribution that provides it, where they differ.
DISTRIBUTIONS = {'win32com': 'pywin32'}
LOCAL = {'joulescope_examples'}


def _imports():
    rv = {}
    for root in ['examples', 'joulescope_examples']:
        for dirpath, _, filenames in os.walk(os.path.join(harness.REPO_PATH, root)):
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, 'rt', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        names = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.level == 0:
                        names = [node.module]
                    else:
                        continue
                    for name in names:
                        top = name.split('.')[0]
                        if top not in sys.stdlib_module_names and top not in LOCAL:
                            rv.setdefault(DISTRIBUTIONS.get(top, top), path)
    return rv


def _requirements():
    rv = set()
    with open(os.path.join(harness.REPO_PATH, 'requirements.txt'), 'rt') as f:
        for line in f:
            line = line.split('#')[0].strip()
            if line:
                rv.add(re.split(r'[<>=!~;\[ ]', line)[0].lower())
    return rv


@pytest.mark.xfail(strict=True, reason='6.20 requirements.txt omits pyjoulescope_driver, pyjls, '
                                       'openpyxl and psutil')
def test_requirements():
    missing = {k: v for k, v in _imports().items() if k.lower() not in _requirements()}
    assert not missing, missing
