# ibl-aws
Utilities to run processing on AWS Cloud

    cd ~/Documents/PYTHON/ibl-sorter/docker
    sudo docker compose exec spikesorter /bin/bash
    sudo docker compose exec spikesorter python /root/Documents/PYTHON/ibl-sorter/examples/run_ibl_recording.py 7ae3865a-d8f4-4b73-938e-ddaec33f8bc6 probe01 --cache_dir /mnt/s0 --scratch_dir /mnt/s0/scratch

## Installation instructions
Install ibl-aws in an environment of your choice:
```shell
cd ibl-aws
pip install -e .
```
Copy the `template.env` file to `.env` and fill with your EC2 access keys

You can make sure the credentials are correct by running the following command:
```python
import iblaws.utils
ec2 = iblaws.utils.get_service_client(service_name='ec2')
ec2.describe_instances()
```


## Installing docker with Nvidia support from a blank EC2

1. Install nvidia drivers
2. Install docker with GPU support
3. Build the docker image and install the container
4. Mount elastic volume that will hold the spike sorting results
5. Whitelist security group
5. Setup ONE



Select an EC2 instance type with Ubuntu on it (P2 or GP3).
Needs to have one system volume of 16 Gb (for the docker build) and an another volume of 800 Gb


1. Install the nvidia drivers (~3mins) - maybe this can be skipped using a EC2 pytorch image
```shell
sudo apt-get update
sudo apt install -y ubuntu-drivers-common
sudo ubuntu-drivers install
sudo reboot
```
It will take a couple of minutes before the instance is available to login again

2. Install Docker with GPU support using the bootstrap script provided (~2mins)

```shell
mkdir -p ~/Documents/PYTHON
cd ~/Documents/PYTHON
git clone -b aws https://github.com/int-brain-lab/ibl-sorter.git
cd ibl-sorter/docker
sudo ./setup_nvidia_container_toolkit.sh
```

3. Format and mount the attached volume, here you want to check that the volume is indeed `/dev/xvdb` using `df -h` (few secs):
```shell
sudo mkfs -t xfs /dev/xvdb
sudo mkdir -p /mnt/s0
sudo mount /dev/xvdb /mnt/s0
sudo chown ubuntu:ubuntu -fR /mnt/s0
df -h
```

4. Build the docker image referring to the instructions above and start the container
# TODO link to ibl-sorter docker readme file

5. Setup ONE from inside the container, make sure the cache directory is `/mnt/s0/spikesorting`, configure the base URL according to your needs,
for internal re-runs it should be set to https://alyx.internationalbrainlab.org
Here is the command to enter the container shell: 
```shell
sudo docker compose exec spikesorter /bin/bash
```

6. If you want to send the data to flatiron you'll have to setup the `~/.ssh/config` file so as to reflect the `sdsc` SSH configuration.