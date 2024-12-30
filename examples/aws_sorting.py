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

ec2 = iblaws.utils.get_boto3_client(service_name='ec2', region_name=INSTANCE_REGION)

iblaws.utils.ec2_start_instance(ec2, INSTANCE_ID)
# %% setup the security group so ONE can communicate with the Alyx database
public_ip = iblaws.utils.ec2_get_public_ip(ec2, INSTANCE_ID)
logger.info(f'Public IP: {public_ip}, ssh command: ssh -i {PRIVATE_KEY_PATH.as_posix()} {USERNAME}@{public_ip}')
ec2_london = iblaws.utils.get_boto3_client(service_name='ec2', region_name='eu-west-2')
iblaws.utils.ec2_update_security_group_rule(
    ec2_london, security_group_id='sg-0ec7c3c71eba340dd', security_group_rule=security_group_rule, new_ip=f'{public_ip}/32'
)

# %% get the SSH client
ssh = iblaws.utils.ec2_get_ssh_client(public_ip, PRIVATE_KEY_PATH, username=USERNAME)
# %% turn the instance on and mount the EBS volumes
logger.info('Mounting EBS volume...')
# the device name listed in the attachment of the EBS volume doesn't match the device name in the /dev/ directory
# but the EBS volume_id is set as the SERIAL number in the device identification, findable using `lsblk -o +SERIAL`
# source: https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html
_, stdout, stderr = ssh.exec_command(f'lsblk -o +SERIAL | grep {volume_id.replace('-', '')}')
device_name = f'/dev/{stdout.read().decode().strip().split()[0]}'
logger.info(f'Device name: {device_name}')
logger.info(f'sudo mount {device_name} /mnt/s0')
_, stdout, stderr = ssh.exec_command(f'sudo mount {device_name} /mnt/s0')


