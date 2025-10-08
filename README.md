# ibl-aws

Deployment of IBL compute on AWS Cloud for the usage of IBL development team.

## Installation instructions
Install ibl-aws in an environment of your choice:
```shell
cd ibl-aws
pip install -e .
```
Copy the `template.env` file to `.env` and fill with your EC2 access keys

You can make sure the credentials are correct by running the following command:
```python
import iblaws.utils
ec2 = iblaws.utils.get_service_client(service_name='ec2')
ec2.describe_instances()
```
