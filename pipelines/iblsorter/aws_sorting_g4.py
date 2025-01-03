from pathlib import Path

import iblutil.util
import iblaws.utils
# 98.84.125.97

logger = iblutil.util.setup_logger('iblaws', level='INFO')

# EC2 instance details
INSTANCE_ID = 'i-05c9c8e9cca199cc7'
INSTANCE_REGION = 'us-east-1'
PRIVATE_KEY_PATH = Path.home().joinpath('.ssh', 'spikesorting_rerun.pem')
USERNAME = 'ubuntu'
# security group that allows ONE to connect to Alyx
security_group_id, security_group_rule = ('sg-0ec7c3c71eba340dd', 'sgr-03801255f4bb69acc')
volume_id = 'vol-0a30864212c68a728'

ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name=INSTANCE_REGION)

# %% starts instance and get its IP
iblaws.utils.ec2_start_instance(ec2, INSTANCE_ID)
public_ip = iblaws.utils.ec2_get_public_ip(ec2, INSTANCE_ID)

# %% setup the security group so ONE can communicate with the Alyx database
logger.info(f'Public IP: {public_ip}, ssh command: ssh -i {PRIVATE_KEY_PATH.as_posix()} {USERNAME}@{public_ip}')
ec2_london = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
iblaws.utils.ec2_update_security_group_rule(
    ec2_london, security_group_id=security_group_id, security_group_rule=security_group_rule, new_ip=f'{public_ip}/32'
)

# %% get the SSH client and mount the EBS volume
ssh = iblaws.utils.ec2_get_ssh_client(public_ip, PRIVATE_KEY_PATH, username=USERNAME)
logger.info('Mounting EBS volume...')
# the device name listed in the attachment of the EBS volume doesn't match the device name in the /dev/ directory
# but the EBS volume_id is set as the SERIAL number in the device identification, findable using `lsblk -o +SERIAL`
# source: https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html
_, stdout, _ = ssh.exec_command(f'lsblk -o +SERIAL | grep {volume_id.replace('-', '')}')
device_name = f'/dev/{stdout.read().decode().strip().split()[0]}'
logger.info(f'Device name: {device_name}')
logger.info(f'sudo mount {device_name} /mnt/s0')
_, stdout, stderr = ssh.exec_command(f'sudo mount {device_name} /mnt/s0')

# %%
eid = 'f2545193-1c5c-420e-96ac-3cb4b9799ea5'
pname = 'probe01'
ssm = iblaws.utils.get_service_client(service_name='ssm', region_name=INSTANCE_REGION)
command = f'/home/ubuntu/entrypoint.sh {eid} {pname}'
command = f'/home/ubuntu/test.sh {eid} {pname}'
# Send a command to the instance
response = ssm.send_command(
    InstanceIds=[INSTANCE_ID],  # replace with your instance ID
    DocumentName='AWS-RunShellScript',
    Parameters={'commands': [command]}  # replace with your command
)

# Get the command ID
command_id = response['Command']['CommandId']
# Get the command output
output = ssm.get_command_invocation(CommandId=command_id, InstanceId=INSTANCE_ID)
print(output['StandardOutputContent'])
#
# import boto3
#
# def list_running_commands(instance_id, region_name='us-west-2'):
#     """
#     List the commands currently running on an EC2 instance.
#
#     :param instance_id: The ID of the EC2 instance.
#     :param region_name: The AWS region where the instance is located (default is 'us-west-2').
#     :return: A list of command IDs that are currently running.
#     """
#     ssm = boto3.client('ssm', region_name=region_name)
#
#     # Get a list of commands sent to the instance
#     commands = ssm.list_commands(InstanceId=instance_id)['Commands']
#
#     running_commands = []
#     for command in commands:
#         # Get the status of each command
#         status = ssm.list_command_invocations(CommandId=command['CommandId'], InstanceId=instance_id)['CommandInvocations'][0]['Status']
#         if status == 'InProgress':
#             running_commands.append(command['CommandId'])
#
#     return running_commands
#
# # Usage example
# running_commands = list_running_commands('i-05c9c8e9cca199cc7')
# print(running_commands)