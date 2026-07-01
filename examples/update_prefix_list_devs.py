# %%
import iblaws.utils
import requests


def get_public_ip():
    response = requests.get('https://api.ipify.org')
    return response.text


# "developers" prefix list, mirrored across regions.
PREFIX_LISTS = {
    'eu-west-2': 'pl-05d04791174282256',
    'us-east-1': 'pl-0eb789aa874fc1952',
}
description = 'Olivier (mobile)'
new_ip = f'{get_public_ip()}/32'

for region_name, prefix_list_id in PREFIX_LISTS.items():
    ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name=region_name)
    iblaws.utils.ec2_update_managed_prefix_list_item(
        ec2, managed_prefix_list_id=prefix_list_id, description=description, cidrip=new_ip
    )
