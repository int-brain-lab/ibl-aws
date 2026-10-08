"""bash
python spike_sort.py bcb1dac7-6d2b-47ad-bbbe-a4aaf9774481

Files are copied to ARTIFACTS_DIR/<pid>, keeping their path relative to the session, at two points:
1. as soon as the sorter has run: the sorter output (spike_sorters/iblsorter/<pname>), before the rest of the task
   (alf conversion, QC, waveforms)
2. before registration: the files to be registered (ssjob.outputs)
In a studio job, every file written under /teamspace/studios/this_studio/ is kept on the teamspace drive under
jobs/<job-name>/, so these files survive even if the job fails.

If ARTIFACTS_DIR/<pid> already holds a sorter output when the job starts, it is restored to the session and ibllib
skips the sorter, as it finds the sorter log there.
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
SORTER_LOG = f'_ibl_log.info_{SpikeSorting.SPIKE_SORTER_NAME}.log'


class CheckpointedSpikeSorting(SpikeSorting):
    """Copies the sorter output to artifacts_dir once the sorter has run, before the rest of the task."""
    artifacts_dir = None

    def _run_iblsort(self, ap_file):
        sorter_dir = super()._run_iblsort(ap_file)
        if self.artifacts_dir is not None:
            dest = self.artifacts_dir.joinpath(sorter_dir.relative_to(self.session_path))
            # the sorter is skipped when its output was restored from the artifacts: nothing new to keep
            if not dest.joinpath(SORTER_LOG).exists():
                print(f'Checkpoint: copying sorter output {sorter_dir} to {dest}')
                shutil.copytree(sorter_dir, dest, dirs_exist_ok=True)
        return sorter_dir


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
                        help=f'Where the sorter output and files to register are kept (default: {ARTIFACTS_DIR})')

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
    # restore the sorter output of a previous run: ibllib then skips the sorter
    sorter_rel = Path('spike_sorters', SpikeSorting.SPIKE_SORTER_NAME, pname)
    saved_sorter_dir, sorter_dir = artifacts_dir.joinpath(sorter_rel), session_path.joinpath(sorter_rel)
    if saved_sorter_dir.joinpath(SORTER_LOG).exists():
        print(f'Restoring sorter output from {saved_sorter_dir} to {sorter_dir}')
        shutil.copytree(saved_sorter_dir, sorter_dir, dirs_exist_ok=True)
    # assert session_path.exists(), f"Session path {session_path} does not exist - exiting..."
    ssjob = CheckpointedSpikeSorting(
        session_path, one=one, pname=pname, device_collection='raw_ephys_data', location='Popeye',
        data_handler_class=LightningAIDataHandler, on_error='raise', scratch_folder=scratch_dir)
    ssjob.artifacts_dir = artifacts_dir
    ssjob.run()
    # keep the files to register, in case the registration fails
    checkpoint(ssjob.outputs, session_path, artifacts_dir)
    ssjob.register_datasets(labs=lab, force=True)
