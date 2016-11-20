# Grab data from Townhall.com

Townhall.com maintains a nice, parseable collection of county-by-county
data on the 2016 election. This script parses it.

## Instructions

Install requirements with a virtualenv.

```bash
virtualenv --python=python3 venv
source venv/bin/activate
pip install -r requirements.txt
```

Run the script.

```bash
python3 grab_from_townhall.py -o data.csv
```
