from pathlib import Path

import iblutil.util
import iblaws.utils
# 98.84.125.97

logger = iblutil.util.setup_logger('iblaws', level='INFO')

# EC2 instance details
INSTANCE_REGION = 'us-east-1'
ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name=INSTANCE_REGION)
ssm = iblaws.utils.get_service_client(service_name='ssm', region_name=INSTANCE_REGION)


# %%
# instance_id = 'i-05c9c8e9cca199cc7'  # g4
# volume_id = 'vol-0a30864212c68a728'  # $0.08/GB-month = $0.11 / TB / hour
# public_ip = start_and_prepare_instance(instance_id, volume_id)
#
# command_id = run_sorting_command(instance_id, pid='b1f22344-6bbc-4540-a4fa-d5e00f9b5857')
#
# response = ssm.get_command_invocation(
#     CommandId=command_id,
#     InstanceId=instance_id,
# )
# TODO have an option to leave the instance running as stopping is slow
# TODO clean up security groups
# https://us-east-1.console.aws.amazon.com/systems-manager/run-command/executing-commands?region=us-east-1

# %%
#instance_id = create_instance()
instance_type = 'g6.4xlarge'
instance_id = 'i-012bf17257acd3f96'  # g6
command = f'/home/ubuntu/entrypoint.sh {pid}'
#g4dn.4xlarge 1.204  g6.4xlarge 1.3232
# instance_id = 'i-05c9c8e9cca199cc7'


# %%
import time
instance_id = 'i-012bf17257acd3f96'  # g6

pids = [
    'b9292b9f-cc04-4d2b-93c0-c0ad16e2b221',
    '5ce945a6-5b59-4d30-8be9-51f6e8280b43',
    '7d5c4c4e-5c23-4a1d-a1ce-32cb79bbcc2a',
    'c52c4943-e764-4a9d-a759-06aff36993f0'
]
for pid in pids:
    command_id = run_sorting_command(instance_id, pid=pid)
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
# response = ec2.describe_instances(
#     Filters=[
#         {
#             'Name': f'tag:Flottille',
#             'Values': ['iblsorter']
#         }
#     ]
# )
# response['Reservations']


commands = ssm.list_commands(
    InstanceId=instance_id,
    MaxResults=10,
    Filters=[
        {
            'key':'ExecutionStage',
            'value': 'Executing',
        }
])['Commands']


# %%
