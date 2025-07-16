# %%
from pathlib import Path
import iblaws.utils

description = 'Charline Tessereau (Mainen)'  # Name Surname Lab
new_ip = '83.240.187.130/32'

# TODO: search for existing entries and propose to clean them up ?
# do not edit below
PREFIX_LIST_ID = 'pl-0be82b42e37cbc052'  # this is the reserachers prefix list
ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
iblaws.utils.ec2_update_managed_prefix_list_item(
    ec2, managed_prefix_list_id=PREFIX_LIST_ID, description=description, cidrip=new_ip
)

# %% If the entry doesn not exist:
iblaws.utils.ec2_add_managed_prefix_list_item(
ec2, managed_prefix_list_id=PREFIX_LIST_ID, description=description, cidrip=new_ip
)
