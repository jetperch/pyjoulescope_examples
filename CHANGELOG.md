
# CHANGELOG

This file contains the list of changes made to pyjoulescope_examples.


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
