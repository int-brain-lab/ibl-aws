#!/bin/bash
set -e
cd Documents/PYTHON/ibl-sorter/docker/
sudo docker compose up -d --no-recreate --remove-orphans
sleep 10
sudo docker compose exec spikesorter git -C /root/Documents/PYTHON/ibllib checkout aws
sudo docker compose exec spikesorter git -C /root/Documents/PYTHON/ibl-sorter checkout aws
sudo docker compose exec spikesorter git -C /root/Documents/PYTHON/ibllib pull
sudo docker compose exec spikesorter git -C /root/Documents/PYTHON/ibl-sorter pull
sudo docker compose exec spikesorter pip install pydantic_settings
sudo docker compose pip install -U ibl-neuropixel
eid=7ae3865a-d8f4-4b73-938e-ddaec33f8bc6
probe_name=probe00
sudo docker compose exec spikesorter python /root/Documents/PYTHON/ibl-sorter/examples/run_ibl_recording.py $eid $probe_name --cache_dir /mnt/s0 --scratch_dir /mnt/s0/scratch
sudo shutdown -h now
