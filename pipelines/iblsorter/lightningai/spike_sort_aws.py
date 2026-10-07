"""bash
python spike_sort.py bcb1dac7-6d2b-47ad-bbbe-a4aaf9774481

Once the sorting has run, the files to be registered (ssjob.outputs) are copied to ARTIFACTS_DIR/<pid>
before the datasets are registered. In a studio job, every file written under /teamspace/studios/this_studio/
is kept on the teamspace drive under jobs/<job-name>/, so these files survive even if the registration fails.
"""

import argparse
import shutil
from pathlib import Path

# NB: ibllightning is found in the ibl-aws package https://github.com/int-brain-lab/ibl-aws
from ibllightning import OneLightningAI as ONE
from ibllightning import LightningAIDataHandler
from ibllib.pipes.ephys_tasks import SpikeSorting

SCRATCH_DIR = Path('/tmp/iblsorter')
ARTIFACTS_DIR = Path('/teamspace/studios/this_studio/artifacts')


def checkpoint(files, session_path, artifacts_dir):
    """Copy files to the artifacts folder, keeping their path relative to the session."""
    for file in map(Path, files):
        dest = artifacts_dir.joinpath(file.relative_to(session_path))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dest)


if __name__ == "__main__":
    # parse arguments with argparse, the first is the eid, the second is the probe name
    parser = argparse.ArgumentParser(description='Run spike sorting on a session')
    parser.add_argument('pid', help='The probe ID')
    parser.add_argument('--scratch-dir', type=Path, default=SCRATCH_DIR,
                        help=f'Scratch directory for temporary files (default: {SCRATCH_DIR})')
    parser.add_argument('--artifacts-dir', type=Path, default=ARTIFACTS_DIR,
                        help=f'Folder where the files to register are kept (default: {ARTIFACTS_DIR})')

    args = parser.parse_args()
    pid = args.pid
    scratch_dir = Path(args.scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = Path(args.artifacts_dir).joinpath(pid)

    one = ONE()
    eid, pname = one.pid2eid(pid)
    session_path = one.eid2path(eid)
    lab = session_path.parts[-5]

    print('eid: ', eid, 'pname: ', pname)
    print('session_path: ', session_path)
    print('scratch_dir: ', scratch_dir)
    print('artifacts_dir: ', artifacts_dir)

    session_path = one.eid2path(eid)
    # assert session_path.exists(), f"Session path {session_path} does not exist - exiting..."
    ssjob = SpikeSorting(session_path, one=one, pname=pname, device_collection='raw_ephys_data', location='Popeye',
                         data_handler_class=LightningAIDataHandler, on_error='raise', scratch_folder=scratch_dir)
    ssjob.run()
    # keep the files to register, in case the registration fails
    checkpoint(ssjob.outputs, session_path, artifacts_dir)
    ssjob.register_datasets(labs=lab, force=True)
