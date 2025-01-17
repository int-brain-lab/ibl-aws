import logging
from pathlib import Path

import iblutil.util
import iblaws.utils


_logger = logging.getLogger(__name__)
PRIVATE_KEY_PATH = Path.home().joinpath('.ssh', 'spikesorting_rerun.pem')
USERNAME = 'ubuntu'

# security group that allows ONE to connect to Alyx
ALYX_SECURITY_GROUP_ID = 'sg-0ec7c3c71eba340dd'


class InstanceManager:

    def __init__(self, instance_id:str, instance_region: str, volume_id: str = 'AWS'):
        self.instance_id = instance_id
        self.instance_region = instance_region
        self.volume_id = volume_id
        self._ssm = None
        self._ec2 = None

    @property
    def ec2(self):
        if self._ec2 is None:
            self._ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name=self.instance_region)
        return self._ec2

    @property
    def ssm(self):
        if self._ssm is None:
            self._ssm = iblaws.utils.get_service_client(service_name='ssm', region_name=self.instance_region)
        return self._ssm


    def start_and_prepare_instance(self) -> str:
        """
        Starts an EC2 instance and prepares it for running the spikesorting pipeline.
        - the function will raise an error if the instance is already running.
        - adds security group rules to allow ONE to communicate with the Alyx database.
        - mounts the EBS volume to the instance

        Args:
            instance_id (str): The ID of the EC2 instance to start.

        Returns:
            str: The public IP address of the started instance.
        """
        # setup the security group so ONE can communicate with the Alyx database
        response = self.ec2.describe_instances(InstanceIds=[self.instance_id])
        instance_state = response['Reservations'][0]['Instances'][0]['State']['Name']
        if instance_state != 'stopped':
            raise ValueError(f'Instance {self.instance_id} is not in stopped state but in {instance_state} state')

        # starts instance and get its IP
        iblaws.utils.ec2_start_instance(self.ec2, self.instance_id)
        public_ip = iblaws.utils.ec2_get_public_ip(self.ec2, self.instance_id)

        # setup the security group so ONE can communicate with the Alyx database
        _logger.info(f'Public IP: {public_ip}, ssh command: ssh -i {PRIVATE_KEY_PATH.as_posix()} {USERNAME}@{public_ip}')
        ec2_london = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
        iblaws.utils.ec2_update_security_group_rule(
            ec2_london,
            security_group_id=ALYX_SECURITY_GROUP_ID,
            description=self.instance_id,
            cidrip=f'{public_ip}/32'
        )
        # get the SSH client and mount the EBS volume
        ssh = iblaws.utils.ec2_get_ssh_client(public_ip, PRIVATE_KEY_PATH, username=USERNAME)
        _logger.info('Mounting EBS volume...')
        # the device name listed in the attachment of the EBS volume doesn't match the device name in the /dev/ directory
        # but the EBS volume_id is set as the SERIAL number in the device identification, findable using `lsblk -o +SERIAL`
        # source: https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html
        _, stdout, _ = ssh.exec_command(f"lsblk -o +SERIAL | grep {self.volume_id.replace('-', '')}")
        device_name = f'/dev/{stdout.read().decode().strip().split()[0]}'
        _logger.info(f'Device name: {device_name}')
        if self.volume_id == 'AWS':
            _logger.info(f'Found device name: {device_name}, now formatting to xfs')
            _, stdout, stderr = ssh.exec_command(f'sudo mkfs -t xfs {device_name}')
        _logger.info(f'Mount device name: {device_name} to /mnt/s0')
        _, stdout, stderr = ssh.exec_command(f'sudo mount {device_name} /mnt/s0')
        _, stdout, _ = ssh.exec_command(f'df -h /mnt/s0')
        _logger.info(stdout.read().decode('utf8').strip())
        _, stdout, stderr = ssh.exec_command(f'sudo mkdir /mnt/s0/scratch')
        return public_ip


    def run_command(self, command: str, time_out_seconds: int = 7_200, comment: str = '') -> str:

        ssm = iblaws.utils.get_service_client(service_name='ssm', region_name=self.instance_region)
        # Send a command to the instance
        response = ssm.send_command(
            InstanceIds=[self.instance_id],  # replace with your instance ID
            DocumentName='AWS-RunShellScript',
            Parameters={
                'commands': [command],
                'executionTimeout': [str(time_out_seconds)],
            },
            TimeoutSeconds=time_out_seconds,  # we give the spike sorting 10 hours to complete
            Comment=comment
        )
        # Get the command ID
        command_id = response['Command']['CommandId']
        return command_id

    @staticmethod
    def create_instance(self, ami_id: str, instance_type: str, instance_region: str, volume_id: str = 'AWS'):
        ec2 = iblaws.utils.get_service_client(service_name='ec2', region_name=instance_region)
        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            KeyName='spikesorting_rerun',  # specify multiple key pairs here, separated by commas
            InstanceInitiatedShutdownBehavior='stop',  # terminate
            # BlockDeviceMappings=[
            #     {
            #         'DeviceName': DEVICE_NAME,
            #         'Ebs': {
            #             'VolumeSize': 512,  # specify the volume size in GB
            #             'DeleteOnTermination': True,  # set to True if you want the volume to be deleted when the instance is terminated
            #             'VolumeType': 'gp3',  # specify the volume type
            #         },
            #     },
            # ],
            IamInstanceProfile={
                # 'Arn': 'arn:aws:iam::537761737250:role/ssm_ec2_receive_commands',
                'Name': 'ssm_ec2_receive_commands'
            },
            TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Flottille',
                        'Value': 'iblsorter'
                    },
                ]
            },
        ],
        )

        instance_id = response['Instances'][0]['InstanceId']
        _logger.info(f"Created instance with ID: {self.instance_id}")
        # bdm = next(item for item in response['Reservations'][0]['Instances'][0]['BlockDeviceMappings'] if item['DeviceName'] == '/dev/sdf')
        # volume_id = bdm['Ebs']['VolumeId']
        public_ip = iblaws.utils.ec2_get_public_ip(self.ec2, self.instance_id)
        # setup the security group so ONE can communicate with the Alyx database
        _logger.info(f'Public IP: {public_ip}, ssh command: ssh -i {PRIVATE_KEY_PATH.as_posix()} {USERNAME}@{public_ip}')
        ec2_london = iblaws.utils.get_service_client(service_name='ec2', region_name='eu-west-2')
        iblaws.utils.ec2_update_security_group_rule(
            ec2_london,
            security_group_id=ALYX_SECURITY_GROUP_ID,
            description=instance_id,
            ip=public_ip
        )

        return InstanceManager(instance_id, instance_region, volume_id)
