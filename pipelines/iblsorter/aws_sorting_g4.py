from pathlib import Path

import iblutil.util
import iblaws.utils
# 98.84.125.97

logger = iblutil.util.setup_logger('iblaws', level='INFO')

# EC2 instance details
INSTANCE_REGION = 'us-east-1'
PRIVATE_KEY_PATH = Path.home().joinpath('.ssh', 'spikesorting_rerun.pem')
USERNAME = 'ubuntu'

# security group that allows ONE to connect to Alyx
ALYX_SECURITY_GROUP_ID = 'sg-0ec7c3c71eba340dd'
ami_id = 'ami-0aee4157817bb44f8'
instance_type = 'g6.4xlarge'  #g4dn.4xlarge 1.204  g6.4xlarge 1.3232
instance_id = 'i-05c9c8e9cca199cc7'
ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name=INSTANCE_REGION)
ssm = iblaws.utils.get_service_client(service_name='ssm', region_name=INSTANCE_REGION)


def start_and_prepare_instance(instance_id: str, volume_id: str = 'AWS') -> str:
    """
    Starts an EC2 instance and prepares it for running the spikesorting pipeline.
    - the function will raise an error if the instance is already running.
    - adds security group rules to allow ONE to communicate with the Alyx database.
    - mounts the EBS volume to the instance

    Args:
        instance_id (str): The ID of the EC2 instance to start.

    Returns:
        str: The public IP address of the started instance.
    """
    # setup the security group so ONE can communicate with the Alyx database
    response = ec2.describe_instances(InstanceIds=[instance_id])
    instance_state = response['Reservations'][0]['Instances'][0]['State']['Name']
    if instance_state != 'stopped':
        raise ValueError(f'Instance {instance_id} is not in stopped state but in {instance_state} state')

    # starts instance and get its IP
    iblaws.utils.ec2_start_instance(ec2, instance_id)
    public_ip = iblaws.utils.ec2_get_public_ip(ec2, instance_id)

    # setup the security group so ONE can communicate with the Alyx database
    logger.info(f'Public IP: {public_ip}, ssh command: ssh -i {PRIVATE_KEY_PATH.as_posix()} {USERNAME}@{public_ip}')
    ec2_london = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
    iblaws.utils.ec2_update_security_group_rule(
        ec2_london, security_group_id=ALYX_SECURITY_GROUP_ID, security_group_rule=alyx_security_group_rule, new_ip=f'{public_ip}/32'
    )

    # get the SSH client and mount the EBS volume
    ssh = iblaws.utils.ec2_get_ssh_client(public_ip, PRIVATE_KEY_PATH, username=USERNAME)
    logger.info('Mounting EBS volume...')
    # the device name listed in the attachment of the EBS volume doesn't match the device name in the /dev/ directory
    # but the EBS volume_id is set as the SERIAL number in the device identification, findable using `lsblk -o +SERIAL`
    # source: https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html
    _, stdout, _ = ssh.exec_command(f"lsblk -o +SERIAL | grep {volume_id.replace('-', '')}")
    device_name = f'/dev/{stdout.read().decode().strip().split()[0]}'
    logger.info(f'Device name: {device_name}')
    logger.info(f'sudo mount {device_name} /mnt/s0')
    ssh.exec_command(f'sudo mount {device_name} /mnt/s0')
    _, stdout, _ = ssh.exec_command(f'df -h /mnt/s0')
    logger.info(stdout.read().decode('utf8').strip())

    return public_ip

def run_sorting_command(instance_id: str, pid: str) -> None:
    ssm = iblaws.utils.get_service_client(service_name='ssm', region_name=INSTANCE_REGION)
    command = f'/home/ubuntu/entrypoint.sh {pid}'
    # Send a command to the instance
    response = ssm.send_command(
        InstanceIds=[instance_id],  # replace with your instance ID
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [command],
            'executionTimeout': ['36000'],
        },
        TimeoutSeconds=3600 * 10,  # we give the spike sorting 10 hours to complete
        Comment=pid
    )
    # Get the command ID
    command_id = response['Command']['CommandId']
    return command_id


def create_instance(volume_id='AWS'):
    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=instance_type,
        MinCount=1,
        MaxCount=1,
        KeyName='spikesorting_rerun',  # specify multiple key pairs here, separated by commas
        InstanceInitiatedShutdownBehavior='stop',  # terminate
        # BlockDeviceMappings=[
        #     {
        #         'DeviceName': DEVICE_NAME,
        #         'Ebs': {
        #             'VolumeSize': 512,  # specify the volume size in GB
        #             'DeleteOnTermination': True,  # set to True if you want the volume to be deleted when the instance is terminated
        #             'VolumeType': 'gp3',  # specify the volume type
        #         },
        #     },
        # ],
        IamInstanceProfile={
            # 'Arn': 'arn:aws:iam::537761737250:role/ssm_ec2_receive_commands',
            'Name': 'ssm_ec2_receive_commands'
        },
        TagSpecifications=[
        {
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': 'Flottille',
                    'Value': 'iblsorter'
                },
            ]
        },
    ],
    )

    instance_id = response['Instances'][0]['InstanceId']
    print(f"Created instance with ID: {instance_id}")
    # bdm = next(item for item in response['Reservations'][0]['Instances'][0]['BlockDeviceMappings'] if item['DeviceName'] == '/dev/sdf')
    # volume_id = bdm['Ebs']['VolumeId']
    public_ip = iblaws.utils.ec2_get_public_ip(ec2, instance_id)

    # setup the security group so ONE can communicate with the Alyx database
    logger.info(f'Public IP: {public_ip}, ssh command: ssh -i {PRIVATE_KEY_PATH.as_posix()} {USERNAME}@{public_ip}')
    ec2_london = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
    iblaws.utils.ec2_create_security_group_rule(
        ec2_london,
        security_group_id=ALYX_SECURITY_GROUP_ID,
        description=instance_id,
        ip=public_ip
    )
    # mounts the attached EBS volume to the instance
    logger.info(f'Formatting and mounting EBS volume...')
    ssh = iblaws.utils.ec2_get_ssh_client(public_ip, PRIVATE_KEY_PATH, username=USERNAME)
    _, stdout, _ = ssh.exec_command(f"lsblk -o +SERIAL | grep {volume_id.replace('-', '')}")
    device_name = f'/dev/{stdout.read().decode().strip().split()[0]}'
    logger.info(f'Found device name: {device_name}, now formatting to xfs')
    _, stdout, stderr = ssh.exec_command(f'sudo mkfs -t xfs {device_name}')
    logger.info(f'Mount device name: {device_name} to /mnt/s0')
    _, stdout, stderr = ssh.exec_command(f'sudo mount {device_name} /mnt/s0')
    _, stdout, stderr = ssh.exec_command(f'sudo mkdir /mnt/s0/scratch')
    return instance_id


# %%
instance_id = 'i-05c9c8e9cca199cc7'  # g4
volume_id = 'vol-0a30864212c68a728'  # $0.08/GB-month = $0.11 / TB / hour
public_ip = start_and_prepare_instance(instance_id, volume_id)

command_id = run_sorting_command(instance_id, pid='b1f22344-6bbc-4540-a4fa-d5e00f9b5857')

response = ssm.get_command_invocation(
    CommandId=command_id,
    InstanceId=instance_id,
)
# TODO have an option to leave the instance running as stopping is slow
# TODO clean up security groups
# https://us-east-1.console.aws.amazon.com/systems-manager/run-command/executing-commands?region=us-east-1

# %%
#instance_id = create_instance()
instance_id = 'i-012bf17257acd3f96'  # g6
# TODO need to get the security group rule ID for the instance
public_ip = start_and_prepare_instance(instance_id, volume_id='AWS')
command_id = run_sorting_command(instance_id, pid='6caafb93-ccbb-4f3d-b339-b262120e9d26')

ec2_london = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')

# response = ec2_london.describe_security_groups(GroupIds=[ALYX_SECURITY_GROUP_ID])
# iblaws.utils.ec2_update_security_group_rule(ec2_london, ALYX_SECURITY_GROUP_ID, 'sgr-006773ff88163e74b', public_ip + '/32')






# %%
response = ec2.describe_instances(
    Filters=[
        {
            'Name': f'tag:Flottille',
            'Values': ['iblsorter']
        }
    ]
)
response['Reservations']


commands = ssm.list_commands(
    InstanceId=instance_id,
    MaxResults=10,
    Filters=[
        {
            'key':'ExecutionStage',
            'value': 'Executing',
        }
])['Commands']
