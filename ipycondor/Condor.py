# Copyright 2019 Mingxuan Lin
# Copyright 2019 Lukas Koschmieder

from __future__ import print_function
import htcondor
from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)

from .ClassAdParser import QueryParser

from IPython.display import display, clear_output
import ipywidgets

from subprocess import Popen, PIPE
import os, time, logging, json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
logger.addHandler(ch)

try:
    import pandas as pd
    import qgrid
except ImportError as ierr:
    logger.warning('Cannot import {s}\nSome functions may fail'.format(ierr))

def my_job_id():
    import re, os
    p = re.compile(r'ClusterId\s+=\s+(\d+)\n')
    try:
        cladname = os.environ['_CONDOR_JOB_AD']
        with open(cladname,'r') as f:
            for line in f:
                m = p.match(line)
                if m:
                    return int(m.group(1))
            logger.error('Fail to find ClusterId attribute in file "%s"', cladname)
            return None
    except (IOError,KeyError) as err:
        logger.debug('%s\nJupyterlab is not started by HTCondor.', str(err))
        return None

def deep_parse(classAds, cols=None):
    parser=QueryParser()
    if cols:
        data = [{c:parser.parse(j, c) for c in cols} for j in classAds]
    else:
        data = [{c:parser.parse(j, c) for c in j} for j in classAds]
    return json.loads(json.dumps(data,default=str))


class TabView(object):
    def __init__(self, f, f_act=None):
        self.f     = f
        self.f_act = f_act

        self.grid_widget = qgrid.show_grid(f(),show_toolbar=False,
                                    grid_options={'editable':False,
                                                  'minVisibleRows':10,
                                                  'maxVisibleRows':8})

        refresh_btn = ipywidgets.Button(description='Refresh',
            icon='refresh', button_style='')
        refresh_btn.on_click(self.refresh)
        self.refresh_btn=refresh_btn

    def refresh(self, *args):
        try:
            self.grid_widget.df = self.f()
        except Exception as err:
            logger.error('Fail to refresh due to an error: %s', err)

    def action(self, *args):
        if not self.f_act: return
        df = self.grid_widget.get_selected_df()
        idxnames = df.index.names
        for idx in df.index:
            argv = dict(zip(idxnames, idx))
            self.f_act(argv)
    @property
    def root_widget(self):
        i=ipywidgets
        return i.VBox([i.HBox( [self.refresh_btn],  layout=i.Layout(justify_content='flex-end') ), self.grid_widget])

class JobView(TabView):
    def __init__(self, f, cdr):
        super().__init__(f, self.job_action)
        self._condor = cdr
        self.act_opt = ipywidgets.Dropdown(
                options=('Suspend','Continue','Hold','Release','Remove'), value='Suspend',
                description='Action:', disabled=False,
            )

        act_btn = ipywidgets.Button( description='Apply' )
        act_btn.on_click(self.action)
        self.act_btn = [self.act_opt, act_btn]

    def job_action(self, job_desc):
        self._condor.job_action(self.act_opt.value, job_desc)
        self.refresh()

    @property
    def root_widget(self):
        i=ipywidgets
        return i.VBox([i.HBox( [i.HBox(self.act_btn), self.refresh_btn  ] , layout=i.Layout(justify_content='flex-end') ),
                       self.grid_widget])

class TabPannel(object):
    _table_layout = tuple()
    def tabs(self):
        _tabs = self._table_layout
        tabs = []
        for t , tab_factory in _tabs:
            tabs.append(tab_factory())
        tab = ipywidgets.Tab(children=tabs)
        for i, t_f in enumerate(_tabs):
            tab.set_title(i, t_f[0])
        self.main_ui_pannel = tab
        return tab

    def dashboard(self):
        c = getattr(self,'main_ui_pannel', None)
        if not c:
            c = self.tabs()
        display(c)



class Condor(TabPannel):
    def __init__(self, schedd_name=None):
        self.coll = htcondor.Collector()
        # schedd_names =  [ s['Name'] for s in coll.locateAll(htcondor.DaemonTypes.Schedd)]
        if schedd_name:
            schedd_ad = self.coll.locate(htcondor.DaemonTypes.Schedd, schedd_name)
        else:
            schedd_ad = self.coll.locate(htcondor.DaemonTypes.Schedd)
        self.schedd = htcondor.Schedd(schedd_ad)
        self._table_layout = [("Jobs", self.job_table), ("Machines", self.machine_table)]
        self.my_job_id = my_job_id()

    def jobs(self, constraint=''):
        return self.schedd.query(constraint.encode())

    def machines(self, constraint=''):
        constraint = 'MyType=="Machine"&&({0})'.format(constraint) if constraint else 'MyType=="Machine"'
        return self.coll.query(constraint=constraint.encode())

    def job_action(self, act,  job_argv):
        if self.my_job_id and self.my_job_id == job_argv.get('ClusterID'):
            return
        act_args = ' && '.join([ '{}=={}'.format(k,v)  for k,v in job_argv.items() ])
        res = self.schedd.act( getattr(htcondor.JobAction, act), act_args )
        return res

    @staticmethod
    def _wrap_tab_hdl(classAds_hdl, constraint, cols, key_cols = [] ):
        columns = tuple(key_cols) + tuple(c for c in cols if c not in key_cols)
        # Create QGrid table widget
        def getdf():
            df = pd.DataFrame(deep_parse(classAds_hdl(constraint), columns), columns=columns)
            if key_cols:
                df = df.set_index(key_cols)
                df = df.sort_index()
            return df
        return getdf

    def job_table(self, constraint='',
             columns=['ClusterID','ProcID','Owner','JobStatus',
                      'JobStartDate','JobUniverse', 'RemoteHost'],
             index=['ClusterID','ProcID']):
        return JobView(self._wrap_tab_hdl(self.jobs,constraint, columns, index), self).root_widget

    def slot_table(self, constraint='',
             columns=['Machine','SlotID','Activity','CPUs','Memory'],
             index=['Machine','SlotID']):
        return TabView(self._wrap_tab_hdl(self.machines,constraint, columns, index)).root_widget


    def machine_table(self,constraint='SlotID==1||SlotID=="1_1"',
            columns=['Machine','TotalSlots','TotalCPUs','TotalMemory',
                     'TotalDisk','TotalLoadAvg'],
            index=['Machine']):
        return TabView(self._wrap_tab_hdl(self.machines,constraint, columns, index)).root_widget

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
        logger.info('[%d]: %s \n%s', p.poll(), out, err)

    @line_magic
    def CondorMon(self,line):
        "Display the Condor dashboard"
        return self.condor.dashboard()

    @property
    def condor(self):
        c = getattr(self,'_condor', None)
        if not isinstance(c, Condor):
            c = Condor()
            self._condor = c
        return c
