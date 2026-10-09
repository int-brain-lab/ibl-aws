"""bash
python spike_sort_aws.py bcb1dac7-6d2b-47ad-bbbe-a4aaf9774481 --scratch-dir /teamspace/scratch/iblsorter

Spike sorting in a Lightning AI job on AWS: the raw data is read from the S3 bucket mounted in the studio.
Checkpointing, resuming and the arguments are in spike_sort.py.
"""
# NB: ibllightning is found in the ibl-aws package https://github.com/int-brain-lab/ibl-aws
from ibllightning import OneLightningAI as ONE
from ibllightning import LightningAIDataHandler

from spike_sort import parse_args, run

if __name__ == "__main__":
    run(parse_args(), ONE(), location='Popeye', data_handler_class=LightningAIDataHandler)
