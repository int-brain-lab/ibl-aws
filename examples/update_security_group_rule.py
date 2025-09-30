"""
This is the way to change the access for lightning AI
Right now it is set to a single IP address for spike sorting testing
"""

import iblaws.utils

# EC2 instance details
security_group_id = 'sg-0ec7c3c71eba340dd'
security_group_rule = 'sgr-04ec3987392de2ac2'
new_ip = '3.87.210.184/32'
ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
iblaws.utils.ec2_update_security_group_rule(ec2, security_group_id, security_group_rule, new_ip)
