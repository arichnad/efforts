
# process-efforts.py

Look through gpx files for your fastest "efforts"

An "effort" is where you ran or biked (etc) for a period of time

Uses your speed sensor data, if that data exists, or uses gps points, if it does not

## usage

* download your gpx files to the `gpx` folder  
(if you're using strava, see https://support.strava.com/hc/en-us/articles/216918437-Exporting-your-Data-and-Bulk-Export)

* run `python3 process-efforts.py`

### command-line options

```
usage: process-efforts.py [-h] [--gpx-dir DIR] [--gpx-filters FILTERS]
                          [--display-only] [--imperial] [--quiet]

generate an effort json from gpx files

optional arguments:
  -h, --help            show this help message and exit
  --gpx-dir DIR         directory containing the gpx files (default: gpx)
  --gpx-filters FILTERS
                        glob filter(s) for the gpx files (default: *.gpx)
  --display-only        only display the json database: do not add files
  --imperial            display imperial distances
  --quiet               quiet output, still displays warnings
```

## python dependencies
* see [requirements.txt](requirements.txt)

### setup

* `pip3 install --user --requirement requirements.txt`

