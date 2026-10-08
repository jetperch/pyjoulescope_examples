
# Joulescope Examples

Welcome to Joulescope™ scripting examples repository! 
Joulescope is an affordable, precision DC energy analyzer that enables you to 
build better products. Joulescope™ accurately and simultaneously measures the 
voltage and current supplied to your target device, and it then computes power 
and energy. For more information on Joulescope, see 
[www.joulescope.com](https://www.joulescope.com).

This joulescope-examples repository contains examples for how to use the
joulescope package in your own Python scripts and programs.  

If you just want to use Joulescope, you can 
[download](https://www.joulescope.com/download) the application.


## Quick start


### Verify Python installation

Verify that Python 3.12 or newer is installed on your computer:

    python3 -VV
    
On Windows, "python3" may not be created by default.  You can try "python -V -V"
if your path is configured correctly, or you can provide the full path to your
python executable.  If python is not already installed on your platform, 
we recommend:

*   Windows: download & install the [official Python release](https://www.python.org/downloads/).
*   macOS: install [brew](https://brew.sh/), then "brew install python"
*   Ubuntu 24.04 LTS: sudo apt install python3 python3-venv


### Get this code

Clone this repository to your computer:

    git clone https://github.com/jetperch/pyjoulescope_examples.git

Alternatively, you can just 
[download the latest](https://github.com/jetperch/pyjoulescope_examples/archive/master.zip) 
version directly from GitHub, and then extract the ZIP file.

Next, cd into the repository directory:

    cd pyjoulescope_examples
    
and install the dependencies:

    pip3 install -U -r requirements.txt

Note that some examples use matplotlib, so be sure to run this last command!

    
### Use this code:

Open a command terminal and run the scripts of your choice.  The examples
directory groups the scripts by the package they demonstrate:

| Directory | Package | Start with |
| --------- | ------- | ---------- |
| [examples/joulescope](examples/joulescope) | joulescope, the high-level API | `capture_simple.py`, `scan.py`, `statistics.py`, `capture_jls.py`, `energy_printer.py` |
| [examples/pyjoulescope_driver](examples/pyjoulescope_driver) | pyjoulescope_driver, the low-level driver | `statistics.py`, `measure.py`, `read.py`, `record.py`, `dut_power.py`, `hotplug.py` |
| [examples/pyjls](examples/pyjls) | pyjls, to read JLS files | `jls_plot.py` |
| [examples/legacy](examples/legacy) | older examples, kept for reference | |

For example:

    python3 examples/joulescope/capture_simple.py

For scripts that take arguments, specify a "--help" argument for details on
the available arguments:

    python3 examples/pyjoulescope_driver/downsample_logging.py --help

Many of the scripts also have instructions inside the script.  Use your 
favorite text editor to open the script.

With several Joulescopes connected, the pyjoulescope_driver examples take
`--device` to select one, such as `--device js220`, `--device 000415` or
`--device js220-000415`.

The scripts used to be in the bin directory.  The bin directory still runs
each script by its old name, such as `python3 bin/scan_by_serial_number.py`.
See [tools/gen_bin_wrappers.py](tools/gen_bin_wrappers.py) for where each one
moved.


## Tests

The tests run each example the way you do, with and without connected
Joulescopes.  See [tests/README.md](tests/README.md).

    python3 -m pip install pytest
    python3 -m pytest -m "not device"


## License

All pyjoulescope_example code is released under the permissive Apache 2.0 
license.  See the [License File](LICENSE.txt) for details.
