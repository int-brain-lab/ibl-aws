"""
DEPRECATED: we use prefix lists for staff and researchers
"""

from pathlib import Path
import iblaws.utils

# EC2 instance details
INSTANCE_ID = 'i-05c9c8e9cca199cc7'
KEY_PAIR_PATH = Path.home().joinpath('spikesorting_rerun.pem')
USERNAME = 'ubuntu'  # This might be different based on your AMI
security_group_id = 'sg-0ec7c3c71eba340dd'
security_group_rule = 'sgr-03801255f4bb69acc'
new_ip = '98.84.125.97/32'
ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
iblaws.utils.ec2_update_security_group_rule(ec2, security_group_id, security_group_rule, new_ip)
