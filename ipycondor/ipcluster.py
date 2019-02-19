""" ipcluster manager for a jupyter notebook """
LICENSE="""
This file is adapted from

`ipyparallel/ipyparallel/nbextension/clustermanager.py`

which is licensed under the terms of the Modified BSD License
(also known as New or Revised or 3-Clause BSD), as follows:

- Copyright (c) 2001-, IPython Development Team
- Copyright (c) 2019-, Mingxuan Lin

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

3. Neither the name of the IPython Development Team nor the names of its
contributors may be used to endorse or promote products derived from this
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import time
from ipyparallel.apps.ipclusterapp import IPClusterStart
class NbIPClusterStart(IPClusterStart):
    """
    `ipcluster start` wraper for notebook
        start:          start controller and engines
        stop_launchers: stop controller and engines
    Parent: https://github.com/ipython/ipyparallel/blob/master/ipyparallel/apps/ipclusterapp.py
    """
    def init_signal(self):
        pass
    def reinit_logging(self):
        pass
    # "Overload the parent's methods because they try to start and stop the global IOLoop object"
    def engines_stopped(self, r): #pylint: disable=W0613
        self.log.info('Engines have stopped')
    def stop_launchers(self, r=None): #pylint: disable=W0613
        if not self._stopping: #pylint: disable=E0203
            self._stopping = True  #pylint: disable=W0201
            self.log.info("IPython cluster: stopping")
            self.stop_controller()
            self.stop_engines()
    def start(self, n=None):
        if isinstance(n,int):
            self.n = n #pylint: disable=W0201
        if self.controller_launcher.state == 'before':
            self.start_controller()
            time.sleep(self.delay)
        if self.engine_launcher.state == 'before':
            self.start_engines()
