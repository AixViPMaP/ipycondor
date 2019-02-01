# Copyright 2019 Lukas Koschmieder
# Copyright 2018 Mingxuan Lin

from __future__ import print_function
import htcondor
from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)

from .Qgrid import to_qgrid
from .JobParser import JobParser
from .MachineParser import MachineParser

from IPython.display import display, clear_output
import ipywidgets as widgets

from subprocess import Popen, PIPE
import os, time

def _load_magic():
    ip = get_ipython()
    ip.register_magics(CondorMagics)

class Table(object):
    def __init__(self, func):
        self.func=func

_tabs = []
def tab(title=""):
    def _wrapper(factory):
        _tabs.append([title, factory])
        return factory
    return _wrapper

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

    @tab("Jobs")
    def job_table(self, constraint='',
             columns=['ClusterID','ProcID','Owner','JobStatus',
                      'JobStartDate','JobUniverse', 'RemoteHost'],
             index=['ClusterID','ProcID']):
        for i in index:
            if not i in columns: columns = [i] + list(columns)
        jobs = self.schedd.query(constraint.encode())
        parser = JobParser()
        data = [[parser.parse(j, c) for c in columns] for j in jobs]
        return to_qgrid(data, columns, index)

    def slot_table(self, constraint='',
             columns=['Machine','SlotID','Activity','CPUs','Memory'],
             index=['Machine','SlotID']):
        for i in index:
            if not i in columns: columns = [i] + list(columns)
        constraint = 'MyType=="Machine"&&({0})'.format(constraint) if constraint else 'MyType=="Machine"'
        machines = self.coll.query(constraint=constraint.encode())
        parser = MachineParser()
        data = [[parser.parse(m, c) for c in columns] for m in machines]
        return to_qgrid(data, columns, index)

    @tab("Machines")
    def machine_table(self):
        return self.slot_table(constraint='SlotID==1||SlotID=="1_1"',
            columns=['Machine','TotalSlots','TotalCPUs','TotalMemory',
                     'TotalDisk','TotalLoadAvg'],
            index=['Machine'])

    def tabs(self):
        tabs = []
        for title , factory in _tabs:
            tabs.append(factory(self))
        tab = widgets.Tab(children=tabs)
        i = 0
        for title , factory in _tabs:
            tab.set_title(i, title)
            i = i + 1
        return tab

    def dashboard(self):
        output = widgets.Output()
        def refresh(button):
            with output:
                index = button.tab.selected_index if hasattr(button, 'tab') else 0
                button.tab = self.tabs()
                button.tab.selected_index = index
                display(button.tab)
                clear_output(wait=True)
        refresh_btn = widgets.Button(description='Refresh', icon='refresh', button_style='')
        refresh_btn.on_click(refresh)
        refresh(refresh_btn)
        controls = widgets.HBox(children=[refresh_btn],
            layout=widgets.Layout(justify_content='flex-end'))
        display(controls, output)
