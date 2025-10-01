import iblaws.compute
import pytest


def test_manage_firewall_access_removes_ip_after_execution(mocker):
    # Mock the AWS service client
    mock_ec2 = mocker.Mock()
    mock_get_service_client = mocker.patch('iblaws.utils.get_service_client', return_value=mock_ec2)

    # Mock the IP getter
    mock_public_ip = '123.45.67.89'
    mocker.patch('iblaws.compute._get_public_ip', return_value=mock_public_ip)

    # Mock the EC2 utility functions
    mock_remove = mocker.patch('iblaws.utils.ec2_remove_managed_prefix_list_item')
    mock_add = mocker.patch('iblaws.utils.ec2_add_managed_prefix_list_item')

    # Create a test function to decorate
    @iblaws.compute.manage_firewall_access(worker=42)
    def test_function():
        return 'result'

    # Call the decorated function
    result = test_function()

    # Verify the function was executed correctly
    assert result == 'result'

    # Verify AWS client was initialized properly
    mock_get_service_client.assert_called_once_with(service_name='ec2', region_name='eu-west-2')

    # Check that the IP was added before execution
    mock_add.assert_called_once_with(
        mock_ec2,
        managed_prefix_list_id=iblaws.compute.HTTPS_PREFIX_LIST_ID,
        description='Lightning AI Worker #42',
        cidrip=f'{mock_public_ip}/32',
    )

    # Verify the IP was removed after execution (which is the main purpose of this test)
    assert mock_remove.call_count == 2  # Called once before (try block) and once after execution
    mock_remove.assert_called_with(
        mock_ec2, managed_prefix_list_id=iblaws.compute.HTTPS_PREFIX_LIST_ID, description='Lightning AI Worker #42'
    )


def test_manage_firewall_access_adds_ip_to_prefix_list(mocker):
    # Mock dependencies
    mock_get_public_ip = mocker.patch('iblaws.compute._get_public_ip', return_value='192.168.1.1')
    mock_get_service_client = mocker.patch('iblaws.utils.get_service_client')
    mock_ec2 = mocker.MagicMock()
    mock_get_service_client.return_value = mock_ec2
    mock_remove_prefix_item = mocker.patch('iblaws.utils.ec2_remove_managed_prefix_list_item')
    mock_add_prefix_item = mocker.patch('iblaws.utils.ec2_add_managed_prefix_list_item')

    # Create a test function and apply the decorator
    @iblaws.compute.manage_firewall_access()
    def test_function():
        return 'test result'

    # Execute the decorated function
    result = test_function(worker_id=42)

    # Verify the decorator behavior
    mock_get_public_ip.assert_called_once()
    mock_get_service_client.assert_called_once_with(service_name='ec2', region_name='eu-west-2')
    mock_remove_prefix_item.assert_called()
    mock_add_prefix_item.assert_called_once_with(
        mock_ec2,
        managed_prefix_list_id=iblaws.compute.HTTPS_PREFIX_LIST_ID,
        description='Lightning AI Worker #42',
        cidrip='192.168.1.1/32',
    )
    assert result == 'test result'
    assert mock_remove_prefix_item.call_count == 2  # Called before and after
