from pathlib import Path
import iblaws.utils
import requests


def get_public_ip():
    response = requests.get('https://api.ipify.org')
    return response.text


PREFIX_LIST_ID = 'pl-05d04791174282256'
description = 'Olivier (mobile)'
ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
new_ip = f'{get_public_ip()}/32'
iblaws.utils.ec2_update_managed_prefix_list_item(
    ec2, managed_prefix_list_id=PREFIX_LIST_ID, description=description, cidrip=new_ip
)
