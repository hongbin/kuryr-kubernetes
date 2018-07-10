# Copyright (c) 2018 Red Hat, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from kuryr_kubernetes import constants
from kuryr_kubernetes.controller.drivers import namespace_security_groups
from kuryr_kubernetes.tests import base as test_base
from kuryr_kubernetes.tests.unit import kuryr_fixtures as k_fix

from neutronclient.common import exceptions as n_exc


def get_pod_obj():
    return {
        'status': {
            'qosClass': 'BestEffort',
            'hostIP': '192.168.1.2',
        },
        'kind': 'Pod',
        'spec': {
            'schedulerName': 'default-scheduler',
            'containers': [{
                'name': 'busybox',
                'image': 'busybox',
                'resources': {}
            }],
            'nodeName': 'kuryr-devstack'
        },
        'metadata': {
            'name': 'busybox-sleep1',
            'namespace': 'default',
            'resourceVersion': '53808',
            'selfLink': '/api/v1/namespaces/default/pods/busybox-sleep1',
            'uid': '452176db-4a85-11e7-80bd-fa163e29dbbb',
            'annotations': {
                'openstack.org/kuryr-vif': {}
            }
        }}


def get_namespace_obj():
    return {
        'metadata': {
            'annotations': {
                constants.K8S_ANNOTATION_NET_CRD: 'net_crd_url_sample'
            }
        }
    }


class TestNamespacePodSecurityGroupsDriver(test_base.TestCase):

    @mock.patch('kuryr_kubernetes.controller.drivers.'
                'namespace_security_groups._get_net_crd')
    @mock.patch('kuryr_kubernetes.config.CONF')
    def test_get_security_groups(self, m_cfg, m_get_crd):
        cls = namespace_security_groups.NamespacePodSecurityGroupsDriver
        m_driver = mock.MagicMock(spec=cls)

        pod = get_pod_obj()
        project_id = mock.sentinel.project_id
        sg_list = [mock.sentinel.sg_id]
        m_cfg.neutron_defaults.pod_security_groups = sg_list
        sg_id = mock.sentinel.sg_id
        extra_sg = mock.sentinel.extra_sg
        net_crd = {
            'spec': {
                'sgId': sg_id
            }
        }
        m_get_crd.return_value = net_crd
        m_driver._get_extra_sg.return_value = [extra_sg]

        ret = cls.get_security_groups(m_driver, pod, project_id)
        expected_sg = [str(sg_id), str(extra_sg), sg_list[0]]

        self.assertEqual(ret, expected_sg)
        m_get_crd.assert_called_once_with(pod['metadata']['namespace'])

    def test_create_namespace_sg(self):
        cls = namespace_security_groups.NamespacePodSecurityGroupsDriver
        m_driver = mock.MagicMock(spec=cls)

        namespace = 'test'
        project_id = mock.sentinel.project_id
        sg = {'id': mock.sentinel.sg}
        subnet_cidr = mock.sentinel.subnet_cidr
        crd_spec = {
            'subnetCIDR': subnet_cidr
        }
        neutron = self.useFixture(k_fix.MockNeutronClient()).client
        neutron.create_security_group.return_value = {'security_group': sg}

        create_sg_resp = cls.create_namespace_sg(m_driver, namespace,
                                                 project_id, crd_spec)

        self.assertEqual(create_sg_resp, {'sgId': sg['id']})
        neutron.create_security_group.assert_called_once()
        neutron.create_security_group_rule.assert_called_once()

    def test_create_namespace_sg_exception(self):
        cls = namespace_security_groups.NamespacePodSecurityGroupsDriver
        m_driver = mock.MagicMock(spec=cls)

        namespace = 'test'
        project_id = mock.sentinel.project_id
        subnet_cidr = mock.sentinel.subnet_cidr
        crd_spec = {
            'subnetCIDR': subnet_cidr
        }
        neutron = self.useFixture(k_fix.MockNeutronClient()).client
        neutron.create_security_group.side_effect = (
            n_exc.NeutronClientException)

        self.assertRaises(n_exc.NeutronClientException,
                          cls.create_namespace_sg, m_driver,
                          namespace, project_id, crd_spec)

        neutron.create_security_group.assert_called_once()
        neutron.create_security_group_rule.assert_not_called()

    def test_delete_sg(self):
        cls = namespace_security_groups.NamespacePodSecurityGroupsDriver
        m_driver = mock.MagicMock(spec=cls)
        neutron = self.useFixture(k_fix.MockNeutronClient()).client

        sg_id = mock.sentinel.sg_id

        cls.delete_sg(m_driver, sg_id)
        neutron.delete_security_group.assert_called_once_with(sg_id)

    def test_delete_sg_exception(self):
        cls = namespace_security_groups.NamespacePodSecurityGroupsDriver
        m_driver = mock.MagicMock(spec=cls)
        neutron = self.useFixture(k_fix.MockNeutronClient()).client

        sg_id = mock.sentinel.sg_id
        neutron.delete_security_group.side_effect = (
            n_exc.NeutronClientException)

        self.assertRaises(n_exc.NeutronClientException, cls.delete_sg,
                          m_driver, sg_id)
        neutron.delete_security_group.assert_called_once_with(sg_id)

    def test_delete_sg_not_found(self):
        cls = namespace_security_groups.NamespacePodSecurityGroupsDriver
        m_driver = mock.MagicMock(spec=cls)
        neutron = self.useFixture(k_fix.MockNeutronClient()).client

        sg_id = mock.sentinel.sg_id
        neutron.delete_security_group.side_effect = n_exc.NotFound

        cls.delete_sg(m_driver, sg_id)
        neutron.delete_security_group.assert_called_once_with(sg_id)
