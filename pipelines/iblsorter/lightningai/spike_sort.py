"""
Code shared by spike_sort_aws.py and spike_sort_gcp.py, which only differ in how ONE is created and in the
SpikeSorting task arguments.

Files are copied to ARTIFACTS_DIR/<pid>, keeping their path relative to the session, at two points:
1. as soon as the sorter has run: the sorter output (spike_sorters/iblsorter/<pname>), before the rest of the task
   (alf conversion, QC, waveforms)
2. once all the output files are written, before the QC labels and plots (which can get stuck): the task's output
   files, as found on disk from its signature
Each file is copied under a temporary name then renamed, so a saved file is always complete.
In a studio job, every file written under /teamspace/studios/this_studio/ is kept on the teamspace drive under
jobs/<job-name>/, so these files survive even if the job fails.

Resuming: with --resume-from <previous job name>, the files saved by that job are read from the teamspace drive,
mounted in the job at /teamspace/jobs/<previous job name>/artifacts/<pid>, and restored to the session:
- if that job saved all the task's required output files (checked against the task signature), they are restored and
  registered: the task is not run, so neither are the QC labels and plots, and no QC images are registered.
- otherwise, if it saved the sorter output, it is restored and the task runs: ibllib skips the sorter, as it finds the
  sorter log there.
"""

import argparse
import shutil
import stat
from pathlib import Path

from ibllib.pipes.ephys_tasks import SpikeSorting

SCRATCH_DIR = Path('/tmp/iblsorter')
ARTIFACTS_DIR = Path('/teamspace/studios/this_studio/artifacts')
JOBS_DIR = Path('/teamspace/jobs')  # the teamspace drive's job folders, as mounted in a job
SORTER_LOG = f'_ibl_log.info_{SpikeSorting._sortername}.log'
# required in the task signature, but not needed for the saved output files to count as complete when resuming
NOT_REQUIRED_TO_RESUME = (f'{SpikeSorting._sortername}_parameters.yaml',)


class CheckpointedSpikeSorting(SpikeSorting):
    """Copies the sorter output to artifacts_dir once the sorter has run, before the rest of the task."""
    artifacts_dir = None
    restored = False  # the sorter output was restored from a previous job: the sorter is skipped, nothing new to keep

    def _run_iblsort(self, ap_file):
        sorter_dir = super()._run_iblsort(ap_file)
        if self.artifacts_dir is not None and not self.restored:
            dest = self.artifacts_dir.joinpath(sorter_dir.relative_to(self.session_path))
            print(f'Checkpoint: copying sorter output {sorter_dir} to {dest}')
            shutil.copytree(sorter_dir, dest, dirs_exist_ok=True)
        return sorter_dir

    def _label_probe_qc(self, *args, **kwargs):
        # all the output files exist at this point, before the QC labels and plots: save them in case those get stuck
        if self.artifacts_dir is not None:
            _, files = signature_outputs(self, self.session_path)
            print(f'Checkpoint: copying {len(files)} output files to {self.artifacts_dir}')
            checkpoint(files, self.session_path, self.artifacts_dir)
        return super()._label_probe_qc(*args, **kwargs)


def restore(src_dir, dest_dir, files=None):
    """
    Copy a folder saved by a previous job, or only some of its files (relative paths). The files under /teamspace/jobs
    are read-only: copy the contents only and make everything writable, as ibllib and phylib open the sorter output
    read-write (a read-only templates.npy is silently skipped by phylib and the alf conversion then fails).
    """
    if files is None:
        shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True, copy_function=shutil.copyfile)
        restored = [dest_dir, *dest_dir.rglob('*')]
    else:
        restored = []
        for rel in files:
            dest_dir.joinpath(rel).parent.mkdir(parents=True, exist_ok=True)
            restored.append(Path(shutil.copyfile(src_dir.joinpath(rel), dest_dir.joinpath(rel))))
    for path in restored:
        path.chmod(path.stat().st_mode | stat.S_IWUSR)


def checkpoint(files, session_path, artifacts_dir):
    """
    Copy files to the artifacts folder, keeping their path relative to the session. Each file is copied under a
    temporary name then renamed, so a saved file is always complete.
    """
    for file in map(Path, files):
        dest = artifacts_dir.joinpath(file.relative_to(session_path))
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + '.part')
        shutil.copy2(file, part)
        part.rename(dest)


def signature_outputs(task, root):
    """
    Find the task's output files to register in root, a session folder or a copy of one saved by a job.
    :return: whether all the required output files are there (except NOT_REQUIRED_TO_RESUME), and the files found
    """
    task.get_signatures()
    complete, files = True, []
    for dataset in task.output_files:
        ok, found, _ = dataset.find_files(root, register=True)
        if not ok and dataset.operator is None and dataset.identifiers[-1] in NOT_REQUIRED_TO_RESUME:
            ok = True
        complete = complete and ok
        files.extend(found)
    return complete, sorted(set(files))


def parse_args():
    parser = argparse.ArgumentParser(description='Run spike sorting on a probe insertion')
    parser.add_argument('pid', help='The probe ID')
    parser.add_argument('--scratch-dir', type=Path, default=SCRATCH_DIR,
                        help=f'Scratch directory for temporary files (default: {SCRATCH_DIR})')
    parser.add_argument('--artifacts-dir', type=Path, default=ARTIFACTS_DIR,
                        help=f'Where the sorter output and files to register are kept (default: {ARTIFACTS_DIR})')
    parser.add_argument('--resume-from', default=None,
                        help='name of a previous job for this pid: registers its saved output files if complete, '
                             'otherwise restores its sorter output and skips the sorter')
    return parser.parse_args()


def run(args, one, **task_kwargs):
    """
    Run spike sorting for args.pid, checkpointing to the artifacts folder, then register the datasets.
    :param args: the parsed arguments, see parse_args
    :param one: the ONE instance
    :param task_kwargs: extra SpikeSorting arguments, e.g. location and data_handler_class
    """
    pid = args.pid
    scratch_dir = Path(args.scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = Path(args.artifacts_dir).joinpath(pid)

    eid, pname = one.pid2eid(pid)
    session_path = one.eid2path(eid)
    lab = session_path.parts[-5]

    print('eid: ', eid, 'pname: ', pname)
    print('session_path: ', session_path)
    print('scratch_dir: ', scratch_dir)
    print('artifacts_dir: ', artifacts_dir)

    ssjob = CheckpointedSpikeSorting(session_path, one=one, pname=pname, device_collection='raw_ephys_data',
                                     on_error='raise', scratch_folder=scratch_dir, **task_kwargs)
    ssjob.artifacts_dir = artifacts_dir
    _ = ssjob.scratch_folder_run  # sets ssjob.version to the iblsorter version, registered with the datasets

    if args.resume_from:
        saved_dir = JOBS_DIR.joinpath(args.resume_from, 'artifacts', pid)
        # 1. the previous job saved all the task's required output files: restore them and only register
        complete, files = signature_outputs(ssjob, saved_dir)
        if complete:
            files = [f.relative_to(saved_dir) for f in files]
            print(f'Restoring the {len(files)} output files from {saved_dir}: the task is not run')
            restore(saved_dir, session_path, files=files)
            ssjob.data_handler = ssjob.get_data_handler()
            ssjob.outputs = [session_path.joinpath(f) for f in files]
            ssjob.register_datasets(labs=lab, force=True)
            return
        # 2. the previous job saved the sorter output: restore it, ibllib then skips the sorter
        sorter_rel = Path('spike_sorters', SpikeSorting._sortername, pname)
        assert saved_dir.joinpath(sorter_rel, SORTER_LOG).exists(), f'Nothing to resume from in {saved_dir}'
        print(f'Restoring sorter output from {saved_dir.joinpath(sorter_rel)} to {session_path.joinpath(sorter_rel)}')
        restore(saved_dir.joinpath(sorter_rel), session_path.joinpath(sorter_rel))
        ssjob.restored = True

    ssjob.run()
    ssjob.register_datasets(labs=lab, force=True)
