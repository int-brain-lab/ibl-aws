import logging
import os
from pathlib import Path
import time
from typing import Optional

import boto3
import dotenv
import iblaws
import paramiko

_logger = logging.getLogger(__name__)


def get_service_client(service_name: str = 'ec2', region_name: Optional[str] = None):
    dotenv.load_dotenv(dotenv_path=Path(iblaws.__file__).parents[2].joinpath('.env'))  # Load environment variables from .env file
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')  # Ensure AWS credentials are loaded
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')  # Ensure AWS credentials are loaded
    AWS_REGION = os.getenv('AWS_REGION')  # Change this to your desired region
    return boto3.client(
        service_name=service_name,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION if region_name is None else region_name,
    )


def ec2_update_security_group_rule(ec2_client, security_group_id: str, description: str, cidrip: str):
    """
    Updates or creates an ingress rule to a security group.

    :param ec2_client:
    :param security_group_id:
    :param description:
    :param cidr: 122.13.123.23/32
    :return:
    """
    response = ec2_client.describe_security_groups(GroupIds=[security_group_id])
    sg = response['SecurityGroups'][0]
    revoke_pip = None

    for pip in sg['IpPermissions']:
        for ir in pip['IpRanges']:
            if ir['Description'] == description:
                _logger.info(f"revoking: {ir['Description']},  {ir['CidrIp']}")
                revoke_pip = pip.copy()
                revoke_pip['IpRanges'] = [ir]
                ec2_client.revoke_security_group_ingress(GroupId=security_group_id, IpPermissions=[revoke_pip])
                revoke_pip['IpRanges'][0]['CidrIp'] = cidrip

    ec2_client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[(revoke_pip or {'IpProtocol': 'all',
                                                  'IpRanges': [{'CidrIp': cidrip, 'Description': description}], })]
    )

    response = ec2_client.describe_security_groups(GroupIds=[security_group_id])
    sg = response['SecurityGroups'][0]
    for pip in sg['IpPermissions']:
        for ir in pip['IpRanges']:
            if ir['Description'] == description:
                _logger.info(f"updated: {ir['Description']},  {ir['CidrIp']}")


def ec2_get_ssh_client(host_ip, key_pair_path, username='ubuntu') -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Wait for SSH to be available
    for i in range(3):  # Try for 5 minutes
        try:
            ssh.connect(host_ip, username=username, key_filename=str(key_pair_path))
            break
        except paramiko.ssh_exception.NoValidConnectionsError:
            time.sleep(5)
    return ssh


def ec2_get_public_ip(ec2_client, instance_id):
    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    return response['Reservations'][0]['Instances'][0]['PublicIpAddress']

import botocore

def ec2_start_instance(ec2_client, instance_id):
    # %% starts the instance if it is not already running
    _logger.info(f'Starting EC2 instance {instance_id}...')
    ec2_client.start_instances(InstanceIds=[instance_id])
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    _logger.info(f'EC2 instance {instance_id} is now running')


def ssm_list_running_commands(instance_id: str, region_name:str = 'us-west-2') -> list:
    """
    List the commands currently running on an EC2 instance.
    :param instance_id: The ID of the EC2 instance.
    :param region_name: The AWS region where the instance is located (default is 'us-west-2').
    :return: A list of command IDs that are currently running.
    """
    ssm = boto3.client('ssm', region_name=region_name)

    # Get a list of commands sent to the instance
    commands = ssm.list_commands(InstanceId=instance_id)['Commands']

    running_commands = []
    for command in commands:
        # Get the status of each command
        status = ssm.list_command_invocations(CommandId=command['CommandId'], InstanceId=instance_id)['CommandInvocations'][0]['Status']
        if status == 'InProgress':
            running_commands.append(command['CommandId'])

    return running_commands
