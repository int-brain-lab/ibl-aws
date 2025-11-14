import logging
import os
from pathlib import Path
import time
from typing import Optional
from difflib import get_close_matches

from pydantic import validate_call, IPvAnyInterface

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
                _logger.info(f'revoking: {ir["Description"]},  {ir["CidrIp"]}')
                revoke_pip = pip.copy()
                revoke_pip['IpRanges'] = [ir]
                ec2_client.revoke_security_group_ingress(GroupId=security_group_id, IpPermissions=[revoke_pip])
                revoke_pip['IpRanges'][0]['CidrIp'] = cidrip

    ec2_client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            (
                revoke_pip
                or {
                    'IpProtocol': 'all',
                    'IpRanges': [{'CidrIp': cidrip, 'Description': description}],
                }
            )
        ],
    )

    response = ec2_client.describe_security_groups(GroupIds=[security_group_id])
    sg = response['SecurityGroups'][0]
    for pip in sg['IpPermissions']:
        for ir in pip['IpRanges']:
            if ir['Description'] == description:
                _logger.info(f'updated: {ir["Description"]},  {ir["CidrIp"]}')


def ec2_get_managed_prefix_list_version(ec2_client, managed_prefix_list_id: str) -> int:
    """
    Get the version of a managed prefix list in AWS EC2.

    Parameters
    ----------
    ec2_client : boto3.client
        The Boto3 EC2 client used to interact with the AWS EC2 service.

    managed_prefix_list_id : str
        The ID of the managed prefix list.

    Returns
    -------
    int
        The version of the managed prefix list.
    """
    list_description = ec2_client.describe_managed_prefix_lists(PrefixListIds=[managed_prefix_list_id]).get('PrefixLists')[0]
    return list_description.get('Version')


@validate_call
def ec2_add_managed_prefix_list_item(ec2_client, managed_prefix_list_id: str, description: str, cidrip: IPvAnyInterface):
    """
    Add a new entry to a managed prefix list in AWS EC2.

    Parameters
    ----------
    ec2_client : boto3.client
        The Boto3 EC2 client used to interact with the AWS EC2 service.

    managed_prefix_list_id : str
        The ID of the managed prefix list.

    description : str
        The description associated with the CIDR entry to be added.

    cidrip : str
        The CIDR block to be added to the managed prefix list.
    """
    list_version = ec2_get_managed_prefix_list_version(ec2_client, managed_prefix_list_id)
    existing_entries = ec2_client.get_managed_prefix_list_entries(PrefixListId=managed_prefix_list_id).get('Entries')
    existing_descriptions = [x['Description'] for x in existing_entries]

    # check if the entry already exists
    if description in existing_descriptions:
        raise ValueError(f'The description "{description}" already exists. Please choose a different description.')

    # add entry
    ec2_client.modify_managed_prefix_list(
        DryRun=False,
        PrefixListId=managed_prefix_list_id,
        CurrentVersion=list_version,
        AddEntries=[{'Cidr': str(cidrip), 'Description': description}],
    )

    # wait for list version to be updated
    while list_version == ec2_get_managed_prefix_list_version(ec2_client, managed_prefix_list_id):
        time.sleep(0.2)
    _logger.info(f'added: {description},  {cidrip}')


@validate_call
def ec2_remove_managed_prefix_list_item(ec2_client, managed_prefix_list_id: str, description: str, ignore_errors: bool = False):
    """
    Remove an entry from a managed prefix list in AWS EC2.

    Parameters
    ----------
    ec2_client : boto3.client
        The Boto3 EC2 client used to interact with the AWS EC2 service.

    managed_prefix_list_id : str
        The ID of the managed prefix list.

    description : str
        The description associated with the CIDR entry to be removed.
    """
    list_version = list_version = ec2_get_managed_prefix_list_version(ec2_client, managed_prefix_list_id)
    existing_entries = ec2_client.get_managed_prefix_list_entries(PrefixListId=managed_prefix_list_id).get('Entries')
    existing_descriptions = [x['Description'] for x in existing_entries]

    if description not in existing_descriptions:
        if ignore_errors:
            return

        close_matches = get_close_matches(description, existing_descriptions, n=5, cutoff=0.6)
        if len(close_matches) == 1:
            suggestion = f'Did you mean "{close_matches[0]}"?'
        elif len(close_matches) > 1:
            suggestion = 'Did you mean one of these: ' + ', '.join([f'"{m}"' for m in close_matches]) + '?'
        else:
            suggestion = ''

        raise ValueError(f'The description "{description}" was not found in the existing entries.' + suggestion)

    remove_entries = [x for x in existing_entries if x['Description'] == description]
    if len(remove_entries) > 0:
        for entry in remove_entries:
            _logger.info(f'removing: {entry["Description"]},  {entry["Cidr"]}')
        ec2_client.modify_managed_prefix_list(
            DryRun=False,
            PrefixListId=managed_prefix_list_id,
            CurrentVersion=list_version,
            RemoveEntries=[{'Cidr': rm['Cidr']} for rm in remove_entries],
        )

    # wait for list version to be updated
    while list_version == ec2_get_managed_prefix_list_version(ec2_client, managed_prefix_list_id):
        time.sleep(0.2)
    _logger.info(f'removed: {description}')


@validate_call
def ec2_update_managed_prefix_list_item(ec2_client, managed_prefix_list_id: str, description: str, cidrip: IPvAnyInterface):
    """
    Update a managed prefix list in AWS EC2 by removing existing entries that match a given description
    and adding a new entry.

    Parameters
    ----------
    ec2_client : boto3.client
        The Boto3 EC2 client used to interact with the AWS EC2 service.

    managed_prefix_list_id : str
        The ID of the managed prefix list to update.

    description : str
        The description associated with the CIDR entry to be added or removed.

    cidrip : str
        The CIDR block to be added to the managed prefix list.
    """
    ec2_remove_managed_prefix_list_item(ec2_client, managed_prefix_list_id, description)
    ec2_add_managed_prefix_list_item(ec2_client, managed_prefix_list_id, description, cidrip)


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


def ec2_stop_instance(ec2_client, instance_id):
    # %% stops the instance if it is running
    _logger.info(f'Stopping EC2 instance {instance_id}...')
    ec2_client.stop_instances(InstanceIds=[instance_id])
    waiter = ec2_client.get_waiter('instance_stopped')
    waiter.wait(InstanceIds=[instance_id])
    _logger.info(f'EC2 instance {instance_id} is now stopped')


def ec2_start_instance(ec2_client, instance_id):
    # %% starts the instance if it is not already running
    _logger.info(f'Starting EC2 instance {instance_id}...')
    ec2_client.start_instances(InstanceIds=[instance_id])
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    _logger.info(f'EC2 instance {instance_id} is now running')


def ssm_list_running_commands(instance_id: str, region_name: str = 'us-west-2') -> list:
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
        status = ssm.list_command_invocations(CommandId=command['CommandId'], InstanceId=instance_id)['CommandInvocations'][0][
            'Status'
        ]
        if status == 'InProgress':
            running_commands.append(command['CommandId'])

    return running_commands
