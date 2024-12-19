from pathlib import Path

import os
import boto3
import time
import paramiko
import dotenv

import iblaws.utils
# 98.84.125.97

# EC2 instance details
INSTANCE_ID = 'i-05c9c8e9cca199cc7'
security_group_id = 'sg-0ec7c3c71eba340dd'
security_group_rule = 'sgr-03801255f4bb69acc'


KEY_PAIR_PATH = Path.home().joinpath('.ssh', 'spikesorting_rerun.pem')
USERNAME = 'ubuntu'  # This might be different based on your AMI


# %% setup the security group so ONE can communicate with the Alyx database
ec2 = iblaws.utils.get_boto3_client(service_name='ec2', region_name='us-east-1')
public_ip = iblaws.utils.get_public_ip(ec2, INSTANCE_ID)
ec2_london = iblaws.utils.get_boto3_client(service_name='ec2', region_name='eu-west-2')
iblaws.utils.update_security_group_rule(ec2_london, security_group_id='sg-0ec7c3c71eba340dd', security_group_rule=security_group_rule, new_ip=f"{public_ip}/32")

# %%
response = ec2.describe_instances(InstanceIds=[INSTANCE_ID])

#
# def start_instance():
#     print("Starting EC2 instance...")
#     ec2.start_instances(InstanceIds=[INSTANCE_ID])
#     waiter = ec2.get_waiter('instance_running')
#     waiter.wait(InstanceIds=[INSTANCE_ID])
#     print("EC2 instance is now running")
#
#
# def stop_instance():
#     print("Stopping EC2 instance...")
#     ec2.stop_instances(InstanceIds=[INSTANCE_ID])
#     waiter = ec2.get_waiter('instance_stopped')
#     waiter.wait(InstanceIds=[INSTANCE_ID])
#     print("EC2 instance is now stopped")


print("Connecting to instance and running script...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Wait for SSH to be available
for i in range(3):  # Try for 5 minutes
    try:
        ssh.connect(public_ip, username=USERNAME, key_filename=str(KEY_PAIR_PATH))
        break
    except paramiko.ssh_exception.NoValidConnectionsError:
        time.sleep(5)

# Run your Python script

stdin, stdout, stderr = ssh.exec_command('python3 /path/to/your/script.py')
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()



