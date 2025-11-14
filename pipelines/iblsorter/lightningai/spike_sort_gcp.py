"""bash
python spike_sort.py bcb1dac7-6d2b-47ad-bbbe-a4aaf9774481
"""

from pathlib import Path
import argparse

from pathlib import Path

from one.api import ONE
from ibllib.pipes.ephys_tasks import SpikeSorting

SCRATCH_DIR = Path('/tmp/iblsorter')
ONE_CACHE_DIR = Path('/tmp/ONE')
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # parse arguments with argparse, the first is the eid, the second is the probe name
    parser = argparse.ArgumentParser(description='Run spike sorting on a session')
    parser.add_argument('pid', help='The probe ID')
    args = parser.parse_args()
    pid = args.pid

    one = ONE(cache_dir=ONE_CACHE_DIR, mode='remote', base_url='https://alyx.internationalbrainlab.org')
    eid, pname = one.pid2eid(pid)
    session_path = one.eid2path(eid)
    lab = session_path.parts[-5]

    print(eid, pname)
    print(session_path)

    session_path = one.eid2path(eid)
    # assert session_path.exists(), f"Session path {session_path} does not exist - exiting..."
    ssjob = SpikeSorting(session_path, one=one, pname=pname, device_collection='raw_ephys_data',
                         location='EC2', on_error='raise', scratch_folder=SCRATCH_DIR)
    ssjob.run()
    ssjob.register_datasets(labs=lab, force=True)
