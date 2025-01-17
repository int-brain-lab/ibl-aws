from pathlib import Path
import time

import iblutil.util
import iblaws.utils
import iblaws.compute
# 98.84.125.97

logger = iblutil.util.setup_logger('iblaws', level='INFO')

# EC2 instance details
INSTANCE_REGION = 'us-east-1'
ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name=INSTANCE_REGION)
ssm = iblaws.utils.get_service_client(service_name='ssm', region_name=INSTANCE_REGION)

# %%
instance_type = 'g6.4xlarge'
instance_id = 'i-012bf17257acd3f96'  # g6
# instance_id = 'i-05c9c8e9cca199cc7'  # g4
# volume_id = 'vol-0a30864212c68a728'  # $0.08/GB-month = $0.11 / TB / hour

im = iblaws.compute.InstanceManager.create_instance(
    ami_id='ami-0aee4157817bb44f8',
    instance_type='g6.4xlarge',
    instance_region='us-east-1'
)

im = iblaws.compute.InstanceManager(instance_id=instance_id, instance_region='us-east-1')
# this will start the instance, add its IP to Alyx security groups and mount the EBS volume
im.start_and_prepare_instance()

# %%
pids = [
    'ba40eda8-601d-41cb-a629-290d17e7a680',
    '18e665b6-cc3d-4cde-980b-ddba405c1b26',
    '4b345c19-4973-4f30-8858-f236e7456553',
    '2631e77a-d521-4939-b247-e7a0ea0a95c1',
    'cbe746bb-8076-41c9-a90e-3bd56b2d958e',
    'becce8b9-db96-4ace-ad99-66397ca9e181',
    '85b98361-9706-4318-8923-6988d4e804e8',
]
for pid in pids:
    command_id = im.run_command(f'/home/ubuntu/entrypoint.sh {pid}')
    logger.critical(f'Started command for pid {pid}, with cid {command_id}...')
    while True:
        time.sleep(600)
        if command_id is None:
            command = next((c for c in ssm.list_commands(InstanceId=instance_id, MaxResults=10)['Commands'] if c['Comment'] == pid))
        else:
            command = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        match command['Status']:
            case 'Success':
                logger.critical(f'Command for pid {pid} completed successfully')
                break
            case 'InProgress':
                logger.info(f'Command for pid {pid} status: {command['Status']}')
                continue
            case _:
                logger.error(f'Command for pid {pid} status: {command['Status']}')
                raise ValueError(f' Weird command status: {command["Status"]}')

# %%
