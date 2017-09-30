#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# (c) 2017, Juan Manuel Parrilla <jparrill@redhat.com>
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = """
---
module: etcd
short_description: Set, Retrieve and delete values from etcd
description:
  - Sets or deletes values in etcd.
  - Parent directories of the key will be created if they do not already exist.
version_added: "2.4"
author: Juan Manuel Parrilla (@padajuan)
requirements:
  - python-etcd >= 0.3.2
options:
  state:
    description:
      - This will be the state of the key in etcd
      - after this module completes its operations.
    required: true
    choices: [present, absent, directory]
    default: null
  protocol:
    description:
      - The scheme to connect to ETCD
    required: false
    default: http
    choices: [http, https]
  host:
    description:
      - The etcd host to use
    required: false
    default: 127.0.0.1
  port:
    description:
      - The port to use on the above etcd host
    required: false
    default: 4001
  api_version:
    description:
      - Api version of ETCD endpoint
    required: false
    default: '/v2'
  key:
    description:
      - The key in etcd at which to set/get the value
    required: true
    default: null
  value:
    description:
      - The value to be set in etcd
    required: false
    default: null
  override:
    description:
      - Force the overwriting of a key-value on etcd
    required: false
    default: false
  allow_redirect:
    description:
      - Etcd attempts to redirect all write requests to the etcd master
      - for safety reasons. If allow_redirect is set to false, such
      - redirection will not be allowed. In this case, the value for `host`
      - must be the etcd leader or this module will err.
    required: false
    default: true
  read_timeout:
    description:
      - Time limit for a read request agains ETCD
    required: false
    default: 60
  cert:
    description:
      - Certificate to connect to an ETCD server with SSL
    required: false
    default: None
  cert_ca:
    description:
      - CA Certificate to connect to an ETCD server with SSL
    required: false
    default: None
  username:
    description:
      - Username to connect to ETCD with RBAC activated
    required: false
    default: None (by default etcd will use guest)
  password:
    description:
      - Password to authenticate to ETCD with RBAC activated
    required: false
    default: None
  recursive:
    description:
      - Used with state:absent, will recursively delete a directory
    required: false
    default: false

notes:
  - Do not override the value stored on ETCD, you must specify it.
  - Based on a module from Rafe Colton
  - Adapted from https://github.com/modcloth-labs/ansible-module-etcd
  - The python-etcd bindings are not still compatible with v1 and v3 of
    ETCD api endpoint, then we will not work with it.
  - I will try to contribute with python-etcd to make it compatible
    with those versions.
"""

EXAMPLES = """
---
# set a value in etcd
- etcd:
    state: present
    host: my-etcd-host.example.com
    port: 4001
    key: /asdf/foo/bar/baz/gorp
    value: my-foo-bar-baz-gor-server.prod.example.com

# delete a value from etcd
- etcd:
    state: absent
    host: my-etcd-host.example.com
    port: 4001
    key: /asdf/foo/bar/baz/gorp

# override an existant ETCD value
- etcd:
    state: present
    host: 127.0.0.1
    port: 2379
    key: "test"
    value: "test_value"
    override: True

# override a value through SSL connection
- etcd:
    state: present
    protocol: https
    host: etcd.globalcorp.com
    port: 2379
    key: "test"
    value: "test_value"
    cert: /path/to/cert
    ca_cert: /path/to/CA
    override: True


# delete an ETCD value with a user and password
- etcd:
    state: absent
    host: 127.0.0.1
    port: 2379
    username: 'user'
    password: 'P4ssW0rd'
"""

RETURN = '''
---
key:
    description: The key quieried
    returned: success
    type: string

value:
    description: The result of the write on ETCD
    returned: sucess
    type: dictionary
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import ConnectionError

try:
    import etcd
    etcd_found = True
except ImportError:
    etcd_found = False


def main():

    module = AnsibleModule(
        argument_spec=dict(
            state=dict(required=True, type='str', choices=['present', 'absent', 'directory']),
            protocol=dict(required=False, type='str', default='http', choices=['http', 'https']),
            host=dict(required=False, type='str', default='127.0.0.1'),
            port=dict(required=False, default=4001, type='int'),
            api_version=dict(required=False, type='str', default='/v2'),
            key=dict(required=True, type='str'),
            value=dict(required=False, default=None),
            override=dict(required=False, type='bool', default=False),
            allow_redirect=dict(required=False, type='bool', default=True),
            read_timeout=dict(required=False, default=60, type='int'),
            cert=dict(required=False, type='str', default=None),
            ca_cert=dict(required=False, type='str', default=None),
            username=dict(required=False, type='str', default=None),
            password=dict(required=False, type='str', default=None, no_log=True),
            recursive=dict(required=False, type='bool', default=False),
        ),
        supports_check_mode=True
    )

    if not etcd_found:
        module.fail_json(msg="the python etcd module is required")

    # For now python-etcd is not compatible with ETCD v1 and v3 api version
    # Contributing on https://github.com/jplana/python-etcd.
    # The entry point at this module is prepared for other versions.
    if module.params['api_version'] != '/v2':
        module.fail_json(msg="This module only support v2 of ETCD, for now")

    # State
    state = module.params['state']

    # Target info
    target_scheme = module.params['protocol']
    target_host = module.params['host']
    target_port = int(module.params['port'])
    target_version = module.params['api_version']

    # K-V
    key = module.params['key']
    value = module.params['value']

    # Config
    override = module.params['override']

    kwargs = {
        'protocol': target_scheme,
        'host': target_host,
        'port': target_port,
        'version_prefix': target_version,
        'allow_redirect': module.params['allow_redirect'],
        'read_timeout': int(module.params['read_timeout']),
        'cert': module.params['cert'],
        'ca_cert': module.params['ca_cert'],
        'username': module.params['username'],
        'password': module.params['password']
    }

    client = etcd.Client(**kwargs)
    results = dict(changed=False, key=key, dir=False)
    prev_value = None

    # Attempt to get key
    try:
        # Getting ETCD Value
        prev_value = client.get(key).value

    except etcd.EtcdKeyNotFound:
        # There is not value on ETCD
        prev_value = None

    # Now get all the data in the key
    try:
        full_record = client.read(key)
        data = dict()
        data['key'] = full_record.key

        if full_record.dir:
            data['dir'] = True
            results['dir'] = True
        else:
            data['value'] = full_record.value
            results['value'] = full_record.value
            data['dir'] = False

        if full_record._children:
            data['children'] = dict()
            for child in full_record._children:
                data['children'][child['key']] = child
        results['data'] = data

    except etcd.EtcdKeyNotFound:
        data = None

    # Handle check mode
    if module.check_mode:
        if state == 'present' and value is None and prev_value is not None:
            results['changed'] = False
        elif ((state == 'absent' and prev_value is not None) or
                (state == 'present' and prev_value != value)):
                    results['changed'] = True
        module.exit_json(**results)

    # we are making a directory
    if state == 'directory':
        if prev_value is None and not results['dir']:
            client.write(key, None, dir=True)
            results['changed'] = True
            results['dir'] = True
        else:
            if results['dir']:
                module.exit_json(**results)
            else:
                module.fail_json(msg="A non-directory key already exists at {0}".format(key))

    # lets handle create mode
    elif state == 'present':
        if prev_value is None:
            if value is None:
                module.fail_json(msg="Key {0} does not exist and new value not provided.".format(key))
            # If 'Present' and there is not a previous value on ETCD
            try:
                set_res = client.write(key, value)
                results['changed'] = True
            except ConnectionError:
                module.fail_json(msg="Cannot connect to target.")
        elif prev_value is not None:
            # If 'Present' and exists a previous value on ETCD
            if prev_value == value or value is None:
                # The value to set, is already present
                results['changed'] = False
            elif override:
                # Trying to Override already existant key on ETCD with flag
                set_res = client.write(key, value)
                results['changed'] = True
            else:
                # Trying to Override already existant key on ETCD without flag
                module.fail_json(msg="The Key '%s' is already set with '%s', exiting..." % (key, prev_value))
        else:
            module.fail_json(msg="prev_value is nonsense")

    # And finally delete mode
    elif state == 'absent':
        if prev_value is None:
            # nothing to do here
            results['changed'] = False
        elif data['dir']:
            # We want to delete a directory
            if data['children'] is None and module.params['recursive']:
                try:
                    client.delete(key, recursive=True)
                except Exception as e:
                    module.fail_json(msg="Directory delete failed: {0}".format(str(e)))
            elif data['children'] is None:
                try:
                    client.delete(key, dir=True)
                except:
                    module.fail_json(msg="Directory {0} has child objects and recursive was not set".format(key))
        else:
            # Not a directory, we want to delete a key, and it has a prev_value
            try:
                set_res = client.delete(key)
                results['changed'] = True
            except ConnectionError:
                module.fail_json(msg="Cannot connect to target.")

    module.exit_json(**results)

if __name__ == "__main__":
    main()
