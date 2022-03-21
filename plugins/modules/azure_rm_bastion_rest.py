#!/usr/bin/python
#
# Copyright: (c) 2022, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
from sys import api_version
__metaclass__ = type


DOCUMENTATION = '''
---
module: azure_rm_bastion_rest

version_added: "0.1.0"

short_description: Manage Azure Bastion service

description:
    - Create, update and delete a Bastion host using REST apis.

options:
    resource_group:
        description:
            - Name of resource group with which the bastion is associated.
        required: true
    virtual_network_name:
        description:
            - Name of the virtual network with which the bastion is associated.
            - required when C(state) is set to I(present).
    public_ip_name:
        description:
            - Name of the public ip address with which the bastion is associated.
            - If not existing will be created using Standard Sku.
            - required when C(state) is set to I(present).
    name:
        description:
            - Name of the Bastion Service.
        required: true
    state:
        description:
            - Assert the state of the Bastion Service. Use C(present) to create or update a and C(absent) to delete.
        default: present
        choices:
            - absent
            - present
    location:
        description:
            - Valid Azure location. Defaults to location of the resource group.
    subnet_address_prefix_cidr:
        description:
            - CIDR defining the IPv4 address space of the azure bastion subnet.
            - Must be valid within the context of the virtual network.
            - Required when the I(AzureBastionSubnet) is not existing.
    api_version:
        description:
            - Specific API version to be used.

extends_documentation_fragment:
    - azure.azcollection.azure
    - azure.azcollection.azure_tags

author:
    - Aubin Bikouo (@abikouo)
'''

EXAMPLES = '''
    - name: Create Azure Bastion service
      azure.azcollection.azure_rm_bastion:
        resource_group: my_resource_group
        name: my_bastion_host
        virtual_network_name: a_virtual_network
        subnet_address_prefix_cidr: xxx.xxx.xxx.xxx/xx
        public_ip_name: a_public_ip_name
    
    - name: Delete Azure Bastion service
      azure.azcollection.azure_rm_bastion:
        resource_group: my_resource_group
        name: my_bastion_host
        state: absent
'''

RETURN = '''
state:
    description:
        - Facts about the current state of the object.
    returned: always
    type: complex
    contains:
        dns_name:
            description:
                - FQDN for the endpoint on which bastion host is accessible.
            returns: always
            type: str
        ip_configurations:
            description:
                - IP configuration of the Bastion Host resource.
            returns: list
            sample: [
                {
                    "name": "ab-azcollection-01-bastion-ip", 
                    "subnet_id": "/subscriptions/3f7e29ba-24e0-42f6-8d9c-5149a14bda37/resourceGroups/ab-azcollection-01/providers/Microsoft.Network/virtualNetworks/ab-azcollection-01-vm-vnet/subnets/AzureBastionSubnet"
                }
            ]
'''
import json
from ansible_collections.azure.azcollection.plugins.module_utils.azure_rm_common import AzureRMModuleBase
from ansible_collections.azure.azcollection.plugins.module_utils.azure_rm_common_rest import GenericRestClient
from msrestazure.azure_exceptions import CloudError

def bastion_to_dict(bastion):
    result = dict(ip_configurations=[])
    if bastion.dns_name:
        result["dns_name"] = bastion.dns_name
    for conf in bastion.ip_configurations:
        result["ip_configurations"].append(
            dict(
                name=conf.name,
                subnet_id=conf.subnet.id,
            )
        )
    return result


class AzureRMBastion(AzureRMModuleBase):

    def __init__(self):

        self.module_arg_spec = dict(
            resource_group=dict(type='str', required=True),
            name=dict(type='str', required=True),
            virtual_network_name=dict(type='str'),
            location=dict(type='str'),
            subnet_address_prefix_cidr=dict(type='str'),
            public_ip_name=dict(type='str'),
            state=dict(type='str', choices=['present', 'absent'], default='present'),
            api_version=dict(),
        )

        self.results = dict(
            changed=False,
        )

        required_if = [
            ('state', 'present', ['virtual_network_name', 'public_ip_name'])
        ]

        self.resource_group = None
        self.name = None
        self.location = None
        self.virtual_network_name = None
        self.subnet_address_prefix_cidr = None
        self.public_ip_name = None
        self.state = None
        self.api_version = None

        super(AzureRMBastion, self).__init__(self.module_arg_spec, required_if=required_if, supports_check_mode=True)

    def get_resource(self, url, api_version, required=False):
        try:
            return json.loads(self.mgmt_client.query(url, "GET", {'api-version': api_version}, None, None, [200], 0, 0).text)
        except CloudError as err:
            if not required and err.status_code == 404:
                return
            self.fail(msg=err.message)
        except Exception as exc:
            self.fail("Failed to get resource group name {0}: {1}".format(self.resource_group, str(exc)))

    def create_resource(self, url, api_version, body=None, headers=None):
        try:
            return json.loads(self.mgmt_client.query(url, "PUT", {'api-version': api_version}, headers, body, [200, 201], 0, 0).text)
        except CloudError as err:
            self.fail(msg="Error creating %s: %s" % (url, err.message))
        except Exception as exc:
            self.fail("Failed to create resource using url {0}: {1}".format(url, str(exc)))

    def delete_resource(self, url, api_version):
        try:
            return json.loads(self.mgmt_client.query(url, "DELETE", {'api-version': api_version}, None, None, [200], 0, 0).text)
        except CloudError as err:
            self.fail(msg="Error deleting %s: %s" % (url, err.message))
        except Exception as exc:
            self.fail("Failed to delete resource using url {0}: {1}".format(url, str(exc)))

    def create_subnet(self):
        changed = False

        name = "AzureBastionSubnet"
        self.log('Fetching subnet {0}'.format(name))
        subnet_api_version = "2021-05-01"
        subnet_url = "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/virtualNetworks/"\
                    "{virtualNetworkName}/subnets/{subnetName}".format(
                        subscriptionId=self.subscription_id,
                        resourceGroupName=self.resource_group,
                        virtualNetworkName=self.virtual_network_name,
                        subnetName=name
                    )
        subnet = self.get_resource(url=subnet_url, api_version=subnet_api_version)
        if not subnet:
            # Create subnet
            changed = True
            if not self.subnet_address_prefix_cidr:
                self.fail("subnet_address_prefix_cidr is required to create bastion subnet {0}".format(name))
            if not self.check_mode:
                body = dict(
                    properties=dict(addressPrefix=self.subnet_address_prefix_cidr)
                )
                subnet = self.create_resource(url=subnet_url, api_version=subnet_api_version, body=body)
        self.subnet_id = subnet.get("id")
        return changed

    def create_public_ip(self):
        changed = False
        api_version = "2021-05-01"
        pip_url = "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}"\
                "/providers/Microsoft.Network/publicIPAddresses/{publicIpAddressName}".format(
            subscriptionId=self.subscription_id, resourceGroupName=self.resource_group,publicIpAddressName=self.public_ip_name
        )

        pip = self.get_resource(url=pip_url, api_version=api_version)
        if not pip:
            # Create Public Ip
            changed = True
            if not self.check_mode:
                body = dict(
                    properties=dict(
                        publicIPAllocationMethod="Static",
                        publicIPAddressVersion="IPv4",
                    ),
                    sku=dict(name="Standard"),
                    location=self.location
                )
                headers = {
                    "Content-Type": 'application/json; charset=utf-8'
                }
                pip = self.create_resource(url=pip_url, api_version=api_version, headers=headers, body=body)
        self.pip_id = pip.get("id")
        return changed

    def create_or_delete_bastion(self):
        changed = False
        api_version = "2021-05-01"
        bastion_url = "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}"\
            "/providers/Microsoft.Network/bastionHosts/{bastionHostName}".format(
                subscriptionId=self.subscription_id, resourceGroupName=self.resource_group, bastionHostName=self.name
            )

        bastion = self.get_resource(url=bastion_url, api_version=api_version)
        if self.state == "present":
            # create bastion host
            if not bastion:
                changed = True
                if not self.check_mode:
                    body = dict(
                        location=self.location,
                        properties=dict(
                            ipConfigurations=[
                                dict(
                                    name=self.public_ip_name,
                                    properties=dict(
                                        subnet=dict(id=self.subnet_id),
                                        publicIPAddress=dict(id=self.pip_id)
                                    )
                                )
                            ]
                        )
                    )
                    headers = {
                        "Content-Type": 'application/json; charset=utf-8'
                    }
                    bastion = self.create_resource(url=bastion_url, headers=headers, api_version=api_version, body=body)
                self.results["state"] = bastion
        else:
            if bastion:
                # delete bastion host
                changed = True
                self.delete_resource(bastion_url, api_version=api_version)

        return changed

    def exec_module(self, **kwargs):

        for key in list(self.module_arg_spec.keys()) + ['tags']:
            setattr(self, key, kwargs[key])

        self.mgmt_client = self.get_mgmt_svc_client(GenericRestClient,
                                                    base_url=self._cloud_environment.endpoints.resource_manager)

        # Get resource group information
        resource_group_url = "/subscriptions/{subscriptionId}/resourcegroups/{resourceGroupName}".format(
            subscriptionId=self.subscription_id,
            resourceGroupName=self.resource_group
        )
        resource = self.get_resource(resource_group_url, api_version='2021-04-01', required=True)
        if not self.location:
            self.location = resource.get("location")

        # create public ip address
        changed = False

        if self.state == "present":
            # Subnet
            changed = self.create_subnet()
            # Public Ip
            changed = self.create_public_ip()
            # Create Bastion Host
            changed = self.create_or_delete_bastion()
        else:
            # Delete Bastion service
            changed = self.create_or_delete_bastion()
        self.results['changed'] = changed
        return self.results


def main():
    AzureRMBastion()


if __name__ == '__main__':
    main()
