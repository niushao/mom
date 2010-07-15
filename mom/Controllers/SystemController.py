# Memory Overcommitment Manager
# Copyright (C) 2010 Adam Litke, IBM Corporation
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

import threading
import time
import logging
from mom.Controllers import Rules

class SystemController(threading.Thread):
    """
    At a regular interval, this thread triggers system reconfiguration by
    sampling host and guest data, evaluating the rule set and reporting the
    results to all enabled Controller plugins.
    """
    def __init__(self, config, rules, libvirt_iface, host_monitor, guest_manager):
        threading.Thread.__init__(self, name="SystemController")
        self.setDaemon(True)
        self.config = config
        self.rules = rules
        self.logger = logging.getLogger('mom.SystemController')
        if rules is None:
            self.logger.warn('%s: No rules were found.', self.getName())
        self.properties = {
            'libvirt_iface': libvirt_iface,
            'host_monitor': host_monitor,
            'guest_manager': guest_manager,
        }
        self.start()
    
    def get_controllers(self):
        """
        Initialize the Controllers called for in the config file.
        """
        self.controllers = []
        config_str = self.config.get('main', 'controllers')
        for name in config_str.split(','):
            name = name.lstrip()
            if name == '':
                continue
            try:
                module = __import__('mom.Controllers.' + name, None, None, name)
                self.logger.debug("Loaded %s controller", name)
            except ImportError:
                self.logger.warn("Unable to import controller: %s", name)
                continue
            self.controllers.append(module.instance(self.properties))

    def do_controls(self):
        """
        Sample host and guest data, process the rule set and feed the results
        into each configured Controller.
        """
        host = self.properties['host_monitor'].interrogate()
        if host is None:
            return
        guest_list = self.properties['guest_manager'].interrogate()
        if Rules.evaluate(self.rules, host, guest_list) is False:
            return
        for c in self.controllers:
            c.process(host, guest_list)

    def run(self):
        self.logger.info("System Controller starting")
        self.get_controllers()
        interval = self.config.getint('main', 'system-controller-interval')
        while self.config.getint('main', 'running') == 1:
            time.sleep(interval)
            self.do_controls()
        self.logger.info("System Controller ending")


