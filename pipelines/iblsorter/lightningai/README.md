# Spike sorting on Lightning AI

Spike sorting runs as Lightning AI jobs, one job per probe insertion (pid). A job is launched from a local computer,
runs `spike_sort_aws.py` or `spike_sort_gcp.py` on a GPU machine started from a studio, sorts the probe with ibllib's
`SpikeSorting` task and registers the datasets. Along the way, the job saves its outputs to the teamspace drive, so that
a failed job can be resumed without rerunning the sorter.

There are two ways to run the workflow:
- [Option 1](#option-1-full-workflow-from-a-terminal): step by step from a Python session in a terminal
- [Option 2](#option-2-with-the-launch_spike_sorting-script): with `examples/launch_spike_sorting.py`

# Setup (once)

## Studios

| | AWS | GCP |
|---|---|---|
| Studio | `iblsorter` | `iblsorter-gcp` |
| Cloud account of the studio | `lightning-public-prod` | `gcp-lightning-public-prod` |
| Machine | `Machine.T4_SMALL` | `Machine.L4` |
| Sorting script | `spike_sort_aws.py` | `spike_sort_gcp.py` |
| [Raw data](#raw-data) | read in place from the S3 bucket mounted in the studio | downloaded by each job with ONE to `/tmp/ONE` |
| [Scratch disk](#scratch-disk-aws-only) | yes, size chosen per job | no |

- AWS studio: the S3 bucket `s3://ibl-brain-wide-map-private/data/` is mounted read-only in the studio at
  `/teamspace/s3_connections/ibl-brain-wide-map-private/data`.
- GCP studio: a copy of the AWS studio, made once in the GCP cloud and named `iblsorter-gcp`. The S3 bucket is not
  mounted there: GCP jobs download the raw data they need, see [Raw data](#raw-data).
- Both studios are in the org `IBL`, teamspace `u19-multi-area-communication`.
- ibl-aws is checked out in each studio at `/teamspace/studios/this_studio/PYTHON/ibl-aws`. A job runs from a snapshot of
  the studio taken when it is launched, so run `git pull` there before launching jobs after a code change. The studio
  does not need to be running for jobs to run.

## Local computer

- A Python environment with ibl-aws installed (`lightning_sdk` and `python-dotenv` come with it).
- Copy `template.env` to `.env` at the root of ibl-aws and set `LIGHTNING_USER_ID` and `LIGHTNING_API_KEY`
  (lightning.ai > profile > Settings > Keys). `.env` is not committed.

# Option 1: full workflow from a terminal

All steps run in one Python session (e.g. `ipython`) on the local computer.

## 1. Start a session and load the credentials

```python
from pathlib import Path
import time
import dotenv

dotenv.load_dotenv(Path('~/int-brain-lab/ibl-aws/.env').expanduser())  # before using lightning_sdk
from lightning_sdk import CloudProvider, Job, Machine, Studio, Teamspace

ORG, TEAMSPACE = 'IBL', 'u19-multi-area-communication'
teamspace = Teamspace(name=TEAMSPACE, org=ORG)
```

## 2. Choose the cloud and connect to its studio

```python
cloud = 'aws'  # or 'gcp'

if cloud == 'aws':
    studio_name, provider, account, machine = 'iblsorter', CloudProvider.AWS, 'lightning-public-prod', Machine.T4_SMALL
else:
    studio_name, provider, account, machine = 'iblsorter-gcp', CloudProvider.GCP, 'gcp-lightning-public-prod', Machine.L4

studio = Studio(name=studio_name, org=ORG, teamspace=TEAMSPACE, cloud=provider, create_ok=False)
assert studio.cloud_account == account  # guards against launching jobs on the wrong cloud
script = f'/teamspace/studios/this_studio/PYTHON/ibl-aws/pipelines/iblsorter/lightningai/spike_sort_{cloud}.py'
```

`create_ok=False` makes a wrong studio or teamspace name an error. Without it, Lightning creates a new empty studio.

## 3. Launch one job per pid

```python
pids = ['168ad7db-...', '49616003-...']  # probe insertion UUIDs
SCRATCH_GB = 500  # AWS only, see Scratch disk below

for i, pid in enumerate(pids):
    if i > 0:
        time.sleep(60)  # avoids hitting the Lightning AI rate limits
    command = f'python {script} {pid}'
    scratch_disks = None
    if cloud == 'aws':
        command += ' --scratch-dir /teamspace/scratch/iblsorter'
        scratch_disks = {'iblsorter': SCRATCH_GB}  # mounted at /teamspace/scratch/iblsorter
    job = Job.run(name=pid, machine=machine, command=command, studio=studio, teamspace=studio.teamspace,
                  cloud=studio.cloud_account, reuse_snapshot=False, scratch_disks=scratch_disks)
    print(pid, job.link)
```

Use `Job.run` rather than `studio.run_job`: only `Job.run` accepts `scratch_disks`. `reuse_snapshot=False` gives each
job a fresh snapshot of the studio.

## 4. Follow the jobs

```python
for job in teamspace.jobs:
    print(job.name, job.status.name)  # e.g. Pending, Running, Completed, Failed, Stopped

job = Job(name=pid, teamspace=teamspace)
job.logs(follow=True)  # stream the job's output
```

To look at a running job's machine (scratch disk, saved files, GPU), connect with SSH from a shell where the `.env`
variables are set:

```shell
set -a; source ~/int-brain-lab/ibl-aws/.env; set +a
lightning job ssh <job name> --teamspace ibl/u19-multi-area-communication
df -h /teamspace/scratch/iblsorter                      # on the job machine (AWS)
ls -lhR /teamspace/studios/this_studio/artifacts/<pid>  # files saved so far
```

## 5. Resume a failed job

Launch a new job for the same pid, as in step 3, adding `--resume-from <previous job name>` to the command:

```python
command = f'python {script} {pid} --resume-from {failed_job_name}'
```

The new job reuses what the failed job saved, see [Resuming](#resuming). Keep the failed job until the new one has
finished: deleting a job deletes its saved files. While the previous job exists, Lightning names the new job
`<pid>-<suffix>`.

## 6. Look at the saved files

```python
job = Job(name=pid, teamspace=teamspace)
for f in job.list_artifacts(path=f'artifacts/{pid}', recursive=True):
    print(f.path, f.size)
job.download_artifacts(target_dir=f'./recovered/{pid}', path=f'artifacts/{pid}')  # can be tens of GB
```

## 7. Clean up

```python
for job in teamspace.jobs:
    if job.status.name == 'Completed':
        job.delete()  # also deletes the job's saved files on the teamspace drive
```

## 8. After the jobs: copy the data from SDSC

This also runs every day as a cron job, so this step is only needed to get the data sooner.

```shell
alyx  # activate environment
python manage.py sync_patcher sync  # run the patching
```

# Option 2: with the launch_spike_sorting script

`examples/launch_spike_sorting.py` runs steps 1 to 3, 5 and 7 of Option 1 from the command line. It reads the
credentials from the ibl-aws `.env`. The teamspace and the per-cloud settings (studio, cloud account, machine, script,
scratch disk) are set at the top of the script, in `TEAMSPACE` and `CLOUDS`.

```shell
cd ~/int-brain-lab/ibl-aws/examples

# launch one job per pid (60 s apart)
python launch_spike_sorting.py launch <pid> [<pid> ...] --scratch-gb 500   # AWS: --scratch-gb is required
python launch_spike_sorting.py launch <pid> [<pid> ...] --cloud gcp        # GCP: no scratch disk

# list the jobs and their status
python launch_spike_sorting.py status

# resume a failed job (one pid at a time)
python launch_spike_sorting.py launch <pid> --scratch-gb 500 --resume-from <previous job name>
python launch_spike_sorting.py launch <pid> --cloud gcp --resume-from <previous job name>

# stop and delete the jobs of a pid, with their saved files (asks for confirmation, --yes to skip it)
python launch_spike_sorting.py delete <pid> [<pid> ...]
```

`delete` also finds the jobs Lightning renamed `<pid>-<suffix>`. To follow the logs, connect with SSH or look at the
saved files, use Option 1 steps 4 and 6. Copying the data from SDSC (Option 1 step 8) runs as a daily cron job, so only
run it by hand to get the data sooner.

# Reference: what a job does

## Scripts

- `spike_sort_aws.py`: creates ONE on the S3 mount (`OneLightningAI`) and runs the task with `location='Popeye'` and
  `LightningAIDataHandler`.
- `spike_sort_gcp.py`: creates ONE in remote mode with its cache in `/tmp/ONE` and runs the task with `location='EC2'`.
- `spike_sort.py`: the code they share. Options of both scripts:
  - `pid`: the probe insertion
  - `--scratch-dir`: where the sorter writes its temporary files (default `/tmp/iblsorter`)
  - `--artifacts-dir`: where the outputs are saved (default `/teamspace/studios/this_studio/artifacts`)
  - `--resume-from`: name of a previous job for this pid to resume from

## Raw data

- AWS: the raw data is read in place from the S3 bucket mounted in the studio
  (`/teamspace/s3_connections/ibl-brain-wide-map-private/data`). Nothing is downloaded.
- GCP: the bucket is not mounted, so at the start of the task each job downloads the probe's raw data with ONE in remote
  mode, from IBL's S3 storage to `/tmp/ONE` on the machine's own disk.

## Scratch disk (AWS only)

The sorter writes large temporary files, such as the whitened copy of the raw data, about the size of the uncompressed
AP file. By default they go to `/tmp/iblsorter` on the machine's own disk, which can be too small.

On AWS, a job can get a scratch disk: an extra, empty disk of a chosen size, created for that job only and deleted when
the job ends, whether it succeeds or fails. It is requested at launch with `Job.run(..., scratch_disks={'iblsorter': GB})`
(`--scratch-gb` in the launch script), mounted at `/teamspace/scratch/iblsorter`, and the sorting script is pointed at
it with `--scratch-dir /teamspace/scratch/iblsorter`. Limits from the SDK: up to 5 disks per job, at most 50 TiB each,
mounted under `/teamspace/scratch/`, studio jobs on a single machine only.

Scratch disks are not available on GCP: GCP jobs are launched without one and the sorter writes to `/tmp/iblsorter` on
the machine's disk. The launch script requires `--scratch-gb` with `--cloud aws` and refuses it with `--cloud gcp`.

Nothing on the scratch disk is kept after the job. Check the space used with `df -h /teamspace/scratch/iblsorter` over SSH.

## Saved outputs

The job saves files to the artifacts folder, `/teamspace/studios/this_studio/artifacts/<pid>`, keeping their path
relative to the session. In a studio job, every file written under `/teamspace/studios/this_studio/` is kept on the
teamspace drive under `jobs/<job name>/`, so the saved files survive the job, until the job is deleted.

`spike_sort.py` runs `CheckpointedSpikeSorting`, a subclass of ibllib's `SpikeSorting`, as a single `ssjob.run()` and
saves at two points:
1. as soon as the sorter has run: the sorter output `spike_sorters/iblsorter/<pname>`, before alf conversion, QC and
   waveforms.
2. once all the output files are written, before the QC labels and plots, which can get stuck: the task's output files
   (alf files, sorter output tar, QC files), found on disk from the task's signature.

Each file is copied under a temporary name and then renamed, so a saved file is always complete.

## Resuming

With `--resume-from <previous job name>`, the job reads what the previous job saved on the teamspace drive, mounted in
jobs at `/teamspace/jobs/<previous job name>/artifacts/<pid>`. Nothing goes through a local computer.
1. If the previous job saved all the task's required output files (checked against the task signature;
   `iblsorter_parameters.yaml` is not required), they are restored and registered without running the task: no QC
   labels, plots or QC images.
2. Otherwise, if it saved the sorter output, it is restored to the session and the task runs: ibllib finds the sorter
   log there and skips the sorter.
3. Otherwise, the job stops with "Nothing to resume from".

The files under `/teamspace/jobs` are read-only. Restored files are made writable, as ibllib and phylib open the sorter
output read-write: phylib silently skips a read-only `templates.npy` and the alf conversion then fails.
