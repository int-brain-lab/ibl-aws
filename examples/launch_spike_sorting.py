"""
Launch iblsorter spike sorting jobs on Lightning AI (AWS or GCP) from a local computer. On AWS, each job gets a
temporary scratch disk of a chosen size (scratch disks are not available on GCP). The job runs spike_sort_aws.py or spike_sort_gcp.py from ibl-aws, which save the
sorter output and the files to register in /teamspace/studios/this_studio/artifacts/<pid>, kept on the teamspace drive
under jobs/<job>/artifacts/<pid>.

Credentials are read from the ibl-aws .env file (LIGHTNING_USER_ID, LIGHTNING_API_KEY).
ibl-aws must be up to date in the studio of the chosen cloud (git pull in the studio).

Usage:
    python launch_spike_sorting.py launch <pid> [<pid> ...] --scratch-gb 500
    python launch_spike_sorting.py launch <pid> --cloud gcp
    python launch_spike_sorting.py status
    python launch_spike_sorting.py launch <pid> --scratch-gb 500 --resume-from <previous job name>
    python launch_spike_sorting.py delete <pid> [<pid> ...] [--yes]

Resuming after a failure: each job saves the sorter output to the drive under jobs/<job>/artifacts/<pid>/.
`launch --resume-from <previous job name>` makes the new job read it there (mounted at /teamspace/jobs) and skip the
sorter. Keep the previous job until the new one has finished: deleting a job deletes its saved files.
"""
import argparse
import time
from pathlib import Path

import dotenv

dotenv.load_dotenv(Path(__file__).parents[1].joinpath('.env'))  # the ibl-aws .env, must run before lightning_sdk calls
from lightning_sdk import CloudProvider, Job, Machine, Studio, Teamspace  # noqa: E402

ORG = 'IBL'
TEAMSPACE = 'u19-multi-area-communication'
SCRIPTS_DIR = '/teamspace/studios/this_studio/PYTHON/ibl-aws/pipelines/iblsorter/lightningai'
# per cloud: studio name, provider, expected cloud account of the studio, machine, sorting script,
# and whether jobs can have a scratch disk (AWS only)
CLOUDS = {
    'aws': dict(studio='iblsorter', provider=CloudProvider.AWS, account='lightning-public-prod',
                machine=Machine.T4_SMALL, script=f'{SCRIPTS_DIR}/spike_sort_aws.py', scratch=True),
    'gcp': dict(studio='iblsorter-gcp', provider=CloudProvider.GCP, account='gcp-lightning-public-prod',
                machine=Machine.L4, script=f'{SCRIPTS_DIR}/spike_sort_gcp.py', scratch=False),
}

SCRATCH_DISK = 'iblsorter'  # mounted at /teamspace/scratch/iblsorter, AWS only
SCRATCH_DIR = f'/teamspace/scratch/{SCRATCH_DISK}'


def get_studio(cloud='aws'):
    conf = CLOUDS[cloud]
    studio = Studio(name=conf['studio'], org=ORG, teamspace=TEAMSPACE, cloud=conf['provider'], create_ok=False)
    assert studio.cloud_account == conf['account'], \
        f"Studio {conf['studio']} is on {studio.cloud_account}, expected {conf['account']}"
    return studio


def build_command(pid, cloud='aws', resume_from=None):
    command = f"python {CLOUDS[cloud]['script']} {pid}"
    if CLOUDS[cloud]['scratch']:
        command += f' --scratch-dir {SCRATCH_DIR}'
    return command + (f' --resume-from {resume_from}' if resume_from else '')


def launch(pids, scratch_gb=None, cloud='aws', resume_from=None, sleep=60):
    assert resume_from is None or len(pids) == 1, '--resume-from takes a single pid'
    if CLOUDS[cloud]['scratch']:
        assert scratch_gb, f'--scratch-gb is required on {cloud}'
        scratch_disks = {SCRATCH_DISK: scratch_gb}
    else:
        assert scratch_gb is None, f'scratch disks are not available on {cloud}: remove --scratch-gb'
        scratch_disks = None
    studio = get_studio(cloud)
    machine = CLOUDS[cloud]['machine']
    jobs = []
    for i, pid in enumerate(pids):
        if i > 0:
            time.sleep(sleep)  # avoids hitting the Lightning AI rate limits
        job = Job.run(
            name=pid,
            machine=machine,
            command=build_command(pid, cloud, resume_from=resume_from),
            studio=studio,
            teamspace=studio.teamspace,
            cloud=studio.cloud_account,
            reuse_snapshot=False,
            scratch_disks=scratch_disks,
        )
        scratch = f'{scratch_gb} GB scratch' if scratch_disks else 'no scratch disk'
        print(f'{pid}: launched on {cloud} {machine.name} with {scratch} - {job.link}')
        jobs.append(job)
    return jobs


def status():
    teamspace = Teamspace(name=TEAMSPACE, org=ORG)
    for job in teamspace.jobs:
        print(f'{job.name:40s} {job.status.name}')


def _confirm(question):
    try:
        return input(f'{question} [y/N] ').strip().lower() == 'y'
    except EOFError:  # no input available: treat as no
        return False


def delete_jobs(pid, yes=False):
    """
    Stop and delete the jobs of a pid: named <pid>, or <pid>-<suffix> when Lightning renamed a relaunch.
    Deleting a job also deletes its artifacts on the teamspace drive.
    """
    jobs = [j for j in Teamspace(name=TEAMSPACE, org=ORG).jobs if j.name == pid or j.name.startswith(f'{pid}-')]
    if not jobs:
        print(f'{pid}: no job found')
    for job in jobs:
        if not yes and not _confirm(f'{job.name}: {job.status.name}, delete the job and its artifacts?'):
            print(f'{job.name}: not deleted')
            continue
        job.stop()  # does nothing if the job already finished
        job.delete()
        print(f'{job.name}: deleted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Spike sorting on Lightning AI')
    sub = parser.add_subparsers(dest='action', required=True)

    p_launch = sub.add_parser('launch', help='launch one job per pid')
    p_launch.add_argument('pids', nargs='+')
    p_launch.add_argument('--scratch-gb', type=int, default=None,
                          help='size of the temporary scratch disk in GB: required on AWS, not available on GCP')
    p_launch.add_argument('--cloud', choices=list(CLOUDS), default='aws', help='cloud provider (default aws)')
    p_launch.add_argument('--resume-from', default=None,
                          help='name of a previous job for this pid: reuse its sorter output and skip the sorter')

    sub.add_parser('status', help='list the jobs in the teamspace')

    p_delete = sub.add_parser('delete', help='stop and delete jobs by pid')
    p_delete.add_argument('pids', nargs='+')
    p_delete.add_argument('--yes', action='store_true', help='do not ask for confirmation')

    args = parser.parse_args()
    if args.action == 'launch':
        launch(args.pids, scratch_gb=args.scratch_gb, cloud=args.cloud, resume_from=args.resume_from)
    elif args.action == 'status':
        status()
    elif args.action == 'delete':
        for pid in args.pids:
            delete_jobs(pid, yes=args.yes)
