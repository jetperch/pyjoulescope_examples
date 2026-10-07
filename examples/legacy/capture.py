#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2020-2025 Jetperch LLC
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


"""Capture Joulescope data to a JLS v2 file.

Instead of this script, consider using pyjoulescope_driver directly, like this:

    python -m pyjoulescope_driver capture out.jls

See https://github.com/jetperch/jls and
https://github.com/jetperch/joulescope_driver/blob/main/pyjoulescope_driver/entry_points/record.py
"""


from pyjoulescope_driver.entry_points import record
import argparse
import sys


def get_parser():
    parser = argparse.ArgumentParser(
        description='Capture streaming samples to a JLS v2 file.',
    )
    parser.add_argument('--jsdrv_log_level',
                        choices=['off', 'emergency', 'alert', 'critical', 'error', 'warning',
                                 'notice', 'info', 'debug1', 'debug2', 'debug3', 'all'],
                        default='error',
                        help='Configure the joulescope driver native log level.')
    record.parser_config(parser)
    return parser


if __name__ == '__main__':
    args = get_parser().parse_args()
    sys.exit(record.on_cmd(args))
