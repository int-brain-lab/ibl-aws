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


def ec2_create_security_group_rule(ec2_client, security_group_id: str, description: str, ip: str):
    """
    Adds an ingress rule to the specified security group.

    Args:
        ec2_client (boto3.client): EC2 client
        security_group_id (str): ID of the security group
        description (str): Description of the rule
        ip (str): IP address range to authorize
    """
    ec2_client.authorize_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {
                'IpProtocol': 'tcp',
                'FromPort': 443,
                'ToPort': 443,
                'IpRanges': [{
                    'CidrIp': f'{ip}/32',
                    'Description': description,
                }],
            },
        ],
    )
    _logger.info(f'Security group rule added successfully with IP {ip} in group {security_group_id}.')


def ec2_update_security_group_rule(ec2_client, security_group_id, security_group_rule, new_ip):
    # Describe the security group to get current rules
    response = ec2_client.describe_security_group_rules(
        Filters=[
            {'Name': 'group-id', 'Values': [security_group_id]},
            {'Name': 'security-group-rule-id', 'Values': [security_group_rule]},
        ]
    )

    if not response['SecurityGroupRules']:
        raise ValueError(f'No rule found with ID {security_group_rule} in security group {security_group_id}')

    rule = response['SecurityGroupRules'][0]

    # Update the rule with the new IP
    ec2_client.modify_security_group_rules(
        GroupId=security_group_id,
        SecurityGroupRules=[
            {
                'SecurityGroupRuleId': security_group_rule,
                'SecurityGroupRule': {
                    'IpProtocol': rule['IpProtocol'],
                    'FromPort': rule['FromPort'],
                    'ToPort': rule['ToPort'],
                    'CidrIpv4': new_ip,
                    'Description': rule.get('Description', ''),
                },
            }
        ],
    )
    _logger.info(
        f'Security group rule {security_group_rule} in group {security_group_id} updated successfully with new IP {new_ip}.'
    )


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
