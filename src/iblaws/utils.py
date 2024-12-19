import os
from pathlib import Path

import boto3
import dotenv
import iblaws


def get_boto3_client(service_name='ec2', region_name=None):

    dotenv.load_dotenv(dotenv_path=Path(iblaws.__file__).parents[2].joinpath('.env'))  # Load environment variables from .env file
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')  # Ensure AWS credentials are loaded
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')  # Ensure AWS credentials are loaded
    AWS_REGION = os.getenv('AWS_REGION')  # Change this to your desired region
    return boto3.client(service_name=service_name, aws_access_key_id=AWS_ACCESS_KEY,
                       aws_secret_access_key=AWS_SECRET_KEY,
                       region_name=AWS_REGION if region_name is None else region_name)



def update_security_group_rule(ec2_client, security_group_id, security_group_rule, new_ip):
    # Describe the security group to get current rules
    response = ec2_client.describe_security_group_rules(
        Filters=[
            {'Name': 'group-id', 'Values': [security_group_id]},
            {'Name': 'security-group-rule-id', 'Values': [security_group_rule]}
        ]
    )

    if not response['SecurityGroupRules']:
        raise ValueError(f"No rule found with ID {security_group_rule} in security group {security_group_id}")

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
                    'Description': rule.get('Description', '')
                }
            }
        ]
    )

    print(f"Security group rule {security_group_rule} in group {security_group_id} updated successfully with new IP {new_ip}.")


def get_public_ip(ec2_client, instance_id):
    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    return response['Reservations'][0]['Instances'][0]['PublicIpAddress']
