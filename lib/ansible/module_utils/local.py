#
# This code is part of Ansible, but is an independent component.
# This particular file snippet, and this file snippet only, is BSD licensed.
# Modules you write using this snippet, which is embedded dynamically by Ansible
# still belong to the author of the module, and may assign their own license
# to the complete work.
#
# (c) 2016 Red Hat Inc.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import json

import ansible.module_utils.basic

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import remove_values

from ansible.errors import AnsibleModuleExit

_ANSIBLE_CONNECTION = None

def _modify_module(task_args, connection):
    params = {'ANSIBLE_MODULE_ARGS': task_args}
    ansible.module_utils.basic._ANSIBLE_ARGS = json.dumps(params)

    global _ANSIBLE_CONNECTION
    _ANSIBLE_CONNECTION = connection

class LocalAnsibleModule(AnsibleModule):

    @property
    def connection(self):
        return _ANSIBLE_CONNECTION

    def exec_command(self, args, check_rc=False):
        '''
        Execute a command, returns rc, stdout, and stderr.
        '''
        rc, out, err = self.connection.exec_command(args)
        if check_rc and rc != 0:
            self.fail_json(msg='command %s failed' % args, rc=rc, stderr=err, stdout=out)
        return rc, out, err

    def exit_json(self, **kwargs):
        ''' return from the module, without error '''
        if not 'changed' in kwargs:
            kwargs['changed'] = False
        if 'invocation' not in kwargs:
            kwargs['invocation'] = {'module_args': self.params}
        kwargs = remove_values(kwargs, self.no_log_values)
        raise AnsibleModuleExit(kwargs)

    def fail_json(self, **kwargs):
        ''' return from the module, with an error message '''
        assert 'msg' in kwargs, "implementation error -- msg to explain the error is required"
        kwargs['failed'] = True
        if 'invocation' not in kwargs:
            kwargs['invocation'] = {'module_args': self.params}
        kwargs = remove_values(kwargs, self.no_log_values)
        raise AnsibleModuleExit(kwargs)
