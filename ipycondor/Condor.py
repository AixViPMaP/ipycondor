# Copyright 2018 Mingxuan Lin

from __future__ import print_function
import htcondor
from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)

from .html import to_html_table
from .JobParser import JobParser

from subprocess import Popen, PIPE
import os, time

def _load_magic():
    try:
        ip = get_ipython()
        ip.register_magics(CondorMagics)
    except:
        pass


@magics_class
class CondorMagics(Magics):

    @cell_magic
    def CondorJob(self, line, cell):
        "Creation of a condor job"
        username=os.environ.get('JUPYTERHUB_USER', os.environ.get('USER'))
        p=Popen( [ 'condor_submit' ] , stdin=PIPE,stdout=PIPE, stderr=PIPE)
        out,err = p.communicate(cell.encode('utf-8'))
        out=out.decode('utf-8','replace')
        err=err.decode('utf-8','replace')
        print(out, '\n', err)
        if p.poll() == 0:
            ui=Condor()
            return ui.job_table(q='Owner=="{0}" && QDate > {1}'.format(username, int(time.time())-30 ))

class Condor(object):
    def __init__(self, schedd_name=None):
        self.coll = htcondor.Collector()
        # schedd_names =  [ s['Name'] for s in coll.locateAll(htcondor.DaemonTypes.Schedd)]
        if schedd_name:
            schedd_ad = self.coll.locate(htcondor.DaemonTypes.Schedd, schedd_name)
        else:
            schedd_ad = self.coll.locate(htcondor.DaemonTypes.Schedd)
        self.schedd = htcondor.Schedd(schedd_ad)


    def job_table(self, q='',
             cols=['ClusterId', 'JobStartDate','Owner','JobStatus', 'JobUniverse', 'DiskUsage', 'RemoteHost']
             ):

        if not 'ClusterId' in cols:  cols = ['ClusterId'] + list(cols)

        jobs = self.schedd.query(q.encode())
        jobs.sort(key=lambda x: x.get('ClusterId', 1e5))
        jobparser = JobParser()

        jobsTab=[[jobparser.parse(j, c) for c in cols] for j in jobs ]

        return to_html_table(jobsTab, cols)


