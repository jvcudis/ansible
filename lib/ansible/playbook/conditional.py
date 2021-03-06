# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
#
# This file is part of Ansible
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

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re

from jinja2.exceptions import UndefinedError

from ansible.compat.six import text_type
from ansible.errors import AnsibleError, AnsibleUndefinedVariable
from ansible.playbook.attribute import FieldAttribute
from ansible.template import Templar
from ansible.module_utils._text import to_native

DEFINED_REGEX = re.compile(r'(hostvars\[.+\]|[\w_]+)\s+(not\s+is|is|is\s+not)\s+(defined|undefined)')

class Conditional:

    '''
    This is a mix-in class, to be used with Base to allow the object
    to be run conditionally when a condition is met or skipped.
    '''

    _when = FieldAttribute(isa='list', default=[])

    def __init__(self, loader=None):
        # when used directly, this class needs a loader, but we want to
        # make sure we don't trample on the existing one if this class
        # is used as a mix-in with a playbook base class
        if not hasattr(self, '_loader'):
            if loader is None:
                raise AnsibleError("a loader must be specified when using Conditional() directly")
            else:
                self._loader = loader
        super(Conditional, self).__init__()

    def _validate_when(self, attr, name, value):
        if not isinstance(value, list):
            setattr(self, name, [ value ])

    def _get_attr_when(self):
        '''
        Override for the 'tags' getattr fetcher, used from Base.
        '''
        when = self._attributes['when']
        if when is None:
            when = []
        if hasattr(self, '_get_parent_attribute'):
            when = self._get_parent_attribute('when', extend=True, prepend=True)
        return when

    def extract_defined_undefined(self, conditional):
        results = []

        cond = conditional
        m = DEFINED_REGEX.search(cond)
        while m:
            results.append(m.groups())
            cond = cond[m.end():]
            m = DEFINED_REGEX.search(cond)

        return results

    def evaluate_conditional(self, templar, all_vars):
        '''
        Loops through the conditionals set on this object, returning
        False if any of them evaluate as such.
        '''

        # since this is a mix-in, it may not have an underlying datastructure
        # associated with it, so we pull it out now in case we need it for
        # error reporting below
        ds = None
        if hasattr(self, '_ds'):
            ds = getattr(self, '_ds')

        try:
            # this allows for direct boolean assignments to conditionals "when: False"
            if isinstance(self.when, bool):
                return self.when

            for conditional in self.when:
                if not self._check_conditional(conditional, templar, all_vars):
                    return False
        except Exception as e:
            raise AnsibleError("The conditional check '%s' failed. The error was: %s" % (to_native(conditional), to_native(e)), obj=ds)

        return True

    def _check_conditional(self, conditional, templar, all_vars):
        '''
        This method does the low-level evaluation of each conditional
        set on this object, using jinja2 to wrap the conditionals for
        evaluation.
        '''

        original = conditional
        if conditional is None or conditional == '':
            return True

        if conditional in all_vars and '-' not in text_type(all_vars[conditional]):
            conditional = all_vars[conditional]

        # make sure the templar is using the variables specified with this method
        templar.set_available_variables(variables=all_vars)

        try:
            conditional = templar.template(conditional)
            if not isinstance(conditional, text_type) or conditional == "":
                return conditional

            # a Jinja2 evaluation that results in something Python can eval!
            presented = "{%% if %s %%} True {%% else %%} False {%% endif %%}" % conditional
            conditional = templar.template(presented)
            val = conditional.strip()
            if val == "True":
                return True
            elif val == "False":
                return False
            else:
                raise AnsibleError("unable to evaluate conditional: %s" % original)
        except (AnsibleUndefinedVariable, UndefinedError) as e:
            # the templating failed, meaning most likely a variable was undefined. If we happened to be
            # looking for an undefined variable, return True, otherwise fail
            try:
                # first we extract the variable name from the error message
                var_name = re.compile(r"'(hostvars\[.+\]|[\w_]+)' is undefined").search(str(e)).groups()[0]
                # next we extract all defined/undefined tests from the conditional string
                def_undef = self.extract_defined_undefined(conditional)
                # then we loop through these, comparing the error variable name against
                # each def/undef test we found above. If there is a match, we determine
                # whether the logic/state mean the variable should exist or not and return
                # the corresponding True/False
                for (du_var, logic, state) in def_undef:
                    # when we compare the var names, normalize quotes because something
                    # like hostvars['foo'] may be tested against hostvars["foo"]
                    if var_name.replace("'", '"') == du_var.replace("'", '"'):
                        # the should exist is a xor test between a negation in the logic portion
                        # against the state (defined or undefined)
                        should_exist = ('not' in logic) != (state == 'defined')
                        if should_exist:
                            return False
                        else:
                            return True
                # as nothing above matched the failed var name, re-raise here to
                # trigger the AnsibleUndefinedVariable exception again below
                raise
            except Exception as new_e:
                raise AnsibleUndefinedVariable("error while evaluating conditional (%s): %s" % (original, e))

