"""bash
python spike_sort_gcp.py bcb1dac7-6d2b-47ad-bbbe-a4aaf9774481

Spike sorting in a Lightning AI job on GCP: the raw data is downloaded with ONE in remote mode to ONE_CACHE_DIR.
Checkpointing, resuming and the arguments are in spike_sort.py.
"""
from pathlib import Path

from one.api import ONE

from spike_sort import parse_args, run

ONE_CACHE_DIR = Path('/tmp/ONE')

if __name__ == "__main__":
    one = ONE(cache_dir=ONE_CACHE_DIR, mode='remote', base_url='https://alyx.internationalbrainlab.org')
    run(parse_args(), one, location='EC2')
