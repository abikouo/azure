#!/usr/bin/python
#
# Copyright: (c) 2022, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = '''
---
module: azure_rm_bastion

version_added: "0.1.0"

short_description: Manage Azure Bastion service

description:
    - Create, update and delete a Bastion host.

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

from ansible_collections.azure.azcollection.plugins.module_utils.azure_rm_common import AzureRMModuleBase
try:
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    # This is handled in azure_rm_common
    pass


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

        super(AzureRMBastion, self).__init__(self.module_arg_spec,
                                             required_if=required_if,
                                             supports_check_mode=True)

    def create_public_ip(self):
        params = dict(
            public_ip_allocation_method="Static",
            public_ip_address_version="IPv4",
            location=self.location,
            sku=self.network_models.PublicIPAddressSku(name="Standard"),
        )
        name = self.public_ip_name
        changed = False
        try:
            self.log("Fetch public ip {0}".format(name))
            pip = self.network_client.public_ip_addresses.get(self.resource_group, name)
            self.check_provisioning_state(pip)
            self.log("Public ip {0} exists".format(name))
            changed=False
        except ResourceNotFoundError:
            self.log('Public ip {0} does not exist'.format(name))
            # Create public ip
            changed = True
            if not self.check_mode:
                try:
                    self.log("Create new Public IP {0}".format(name))
                    pip = self.network_models.PublicIPAddress(**params)
                    poller = self.network_client.public_ip_addresses.begin_create_or_update(self.resource_group, name, pip)
                    pip = self.get_poller_result(poller)
                except Exception as exc:
                    self.fail("Error creating public ip {0} - {1}".format(name, str(exc)))
        self.pip_id = pip.id
        return changed

    def create_subnet(self):
        changed = False
        try:
            name = "AzureBastionSubnet"
            self.log('Fetching subnet {0}'.format(name))
            subnet = self.network_client.subnets.get(self.resource_group,
                                                     self.virtual_network_name,
                                                     name)
            self.check_provisioning_state(subnet)
        except ResourceNotFoundError:
            # the subnet does not exist, create it
            if not self.subnet_address_prefix_cidr:
                self.fail("subnet_address_prefix_cidr is required to create bastion subnet {0}".format(name))
            changed = True
            if not self.check_mode:
                try:
                    # Create new subnet
                    self.log('Creating subnet {0}'.format(name))
                    subnet_params = self.network_models.Subnet(
                        address_prefix=self.subnet_address_prefix_cidr,
                    )
                    poller = self.network_client.subnets.begin_create_or_update(self.resource_group,
                                                                                self.virtual_network_name,
                                                                                name,
                                                                                subnet_params)
                    subnet = self.get_poller_result(poller)
                except Exception as exc:
                    self.fail("Error creating subnet {0} - {1}".format(name, str(exc)))
        self.subnet_id = subnet.id
        return changed

    def create_or_delete_bastion(self):
        changed = False
        try:
            self.log('Fetching bastion hosts {0}'.format(self.name))
            bastion = self.network_client.bastion_hosts.get(resource_group_name=self.resource_group,
                                                            bastion_host_name=self.name)
            self.check_provisioning_state(bastion, requested_state=self.state)
            if self.state == "absent":
                # Delete Bastion
                changed = True
                if not self.check_mode:
                    try:
                        self.log('Deleting bastion host {0}'.format(self.name))
                        poller = self.network_client.bastion_hosts.begin_delete(self.resource_group,self.name)
                        self.get_poller_result(poller)
                    except Exception as exc:
                        self.fail("Error deleting bastion {0} - {1}".format(self.name, str(exc)))
            else:
                self.results["state"] = bastion_to_dict(bastion)
        except ResourceNotFoundError:
            # the bastion host does not exist
            if self.state == "present":
                changed = True
                if not self.check_mode:
                    try:
                        self.log('Creating bastion host {0}'.format(self.name))
                        ip_configuration = self.network_models.BastionHostIPConfiguration(
                            name=self.public_ip_name,
                            public_ip_address=self.network_models.SubResource(id=self.pip_id),
                            subnet=self.network_models.SubResource(id=self.subnet_id),
                        )
                        bastionhost = self.network_models.BastionHost(
                            location=self.location,
                            ip_configurations=[ip_configuration],
                        )
                        poller = self.network_client.bastion_hosts.begin_create_or_update(self.resource_group,
                                                                                          self.name,
                                                                                          bastionhost)
                        new_bastion_host = self.get_poller_result(poller)
                        self.results["state"] = bastion_to_dict(new_bastion_host)
                    except Exception as exc:
                        self.fail("Error creating bastion {0} - {1}".format(self.name, str(exc)))
        return changed

    def exec_module(self, **kwargs):

        for key in list(self.module_arg_spec.keys()) + ['tags']:
            setattr(self, key, kwargs[key])

        resource_group = self.get_resource_group(self.resource_group)
        if not self.location:
            # Set default location
            self.location = resource_group.location

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
