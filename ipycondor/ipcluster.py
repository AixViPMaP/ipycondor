""" ipcluster manager for a jupyter notebook """
# Copyright 2019 Mingxuan Lin

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
