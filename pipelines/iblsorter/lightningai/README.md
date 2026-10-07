# Setup 
## AWS studio Setup

The S3 bucket `s3://ibl-brain-wide-map-private/data/` should be mounted in read-only mode in the studio at `/teamspace/s3_connections/ibl-brain-wide-map-private/data`

## GCP studio Setup
In lightning AI, make sure you copy the studio once into the GCP cloud and give it a different name. 
For spike sorting, it is `iblsorter-gcp`.

# Usage

## Choosing the cloud backend

Two cloud backends are supported: **GCP** (default) and **AWS**. The scripts are distinct for each case to account for the copy locations.

| Backend | Machine | Studio name | Script |
|---------|---------|-------------|--------|
| GCP | `Machine.L4` | `iblsorter-gcp` | `spike_sort_gcp.py` |
| AWS | `Machine.T4_SMALL` | `iblsorter` | `spike_sort_aws.py` |

Select the backend by uncommenting the appropriate line at the top of your launcher script:

```python
from lightning_sdk import Machine, Studio, Teamspace, CloudProvider

machine, cloud_provider = (Machine.L4, CloudProvider.GCP)
# machine, cloud_provider = (Machine.T4_SMALL, CloudProvider.AWS)

studio_name = 'iblsorter' if cloud_provider == CloudProvider.AWS else 'iblsorter-gcp'
script = f'spike_sort_{str(cloud_provider).lower()}.py'

s = Studio(name=studio_name, org='IBL', teamspace=TEAMSPACE, cloud=cloud_provider, create_ok=False)
assert str(cloud_provider).lower() in s.cloud_account  # sanity-check the cloud account matches
```

The assertion on the last line guards against accidentally submitting jobs to the wrong cloud account.

## Submitting spike-sorting jobs

Pass a list of PIDs and submit one job per PID. A 60-second sleep between submissions avoids hitting Lightning AI rate limits:

```python
import time

pids = ['168ad7db-...', '49616003-...']  # list of probe insertion UUIDs

for pid in pids:
    cmd = (f'python /teamspace/studios/this_studio/PYTHON/ibl-aws/'
           f'pipelines/iblsorter/lightningai/{script} {pid}')
    s.run_job(command=cmd, machine=machine, name=pid, reuse_snapshot=False)
    time.sleep(60)
```

## Keeping the outputs if the registration fails

Once the sorting has run, `spike_sort_aws.py` and `spike_sort_gcp.py` copy the files to be registered (`ssjob.outputs`: the alf files and
the sorter output tar) to `/teamspace/studios/this_studio/artifacts/<pid>` (`--artifacts-dir`), keeping their path
relative to the session, before calling `register_datasets`. In a studio job, files written under `this_studio/` are
kept on the teamspace drive under `jobs/<job-name>/`. Nothing from the scratch folder is kept.
To recover the artifacts from a local computer:

```python
from lightning_sdk import Job, Teamspace
job = Job(name=pid, teamspace=Teamspace(name=TEAMSPACE, org='IBL'))
job.download_artifacts(target_dir=f'./recovered/{pid}', path=f'artifacts/{pid}')
```

To check job statuses and clean up completed jobs:

```python
for job in s.teamspace.jobs:
    if job.status.name == 'Completed':
        print(job.name, 'Completed')
        job.delete()
```

Some possible status values: `"Failed"`, `"Stopped"`, `"Completed"`.


## After the job: copying the data from SDSC
```shell
alyx  # activate environment
python manage.py sync_patcher sync # run the patching
```