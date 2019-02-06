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
        logger.debug('%s\n\tJupyterlab is not started by HTCondor.', str(err))
        return None

def deep_parse(classAds, cols=None):
    parser=QueryParser()
    if cols:
        data = [{c:parser.parse(j, c) for c in cols} for j in classAds]
    else:
        data = [{c:parser.parse(j, c) for c in j} for j in classAds]
    return data

class TabView(object):
    def __init__(self, f, log=logger):
        self.f   = f
        self.log = log
        self.grid_widget = qgrid.show_grid(f(),show_toolbar=False,
                                    grid_options={'editable':False,
                                                  'minVisibleRows':8,
                                                  'maxVisibleRows':10})

        refresh_btn = ipywidgets.Button(description='Refresh',
            icon='refresh', button_style='')
        refresh_btn.on_click(self.refresh)
        self.refresh_btn=refresh_btn

    def refresh(self, *args):
        try:
            self.grid_widget.df = self.f()
        except Exception as err:
            self.log.error('Fail to refresh due to an error: %s', err)

    def action(self, *args):
        """ Callback for applying action on slected rows """
        df = self.grid_widget.get_selected_df()
        idxnames = df.index.names
        for idx in df.index:
            self.f_act(dict(zip(idxnames, idx)))

    def f_act(self, row_index):
        """ Applying action on a row (called by self.action) """
        raise NotImplementedError("Please override f_act in your subclass")

    @property
    def root_widget(self):
        i=ipywidgets
        return i.VBox([i.HBox( [self.refresh_btn],  layout=i.Layout(justify_content='flex-end') ), self.grid_widget])

class JobView(TabView):
    def __init__(self, f, cdr, **argv):
        super().__init__(f,**argv)
        self._condor = cdr
        self.act_opt = ipywidgets.Dropdown(
                options=('Suspend','Continue','Hold','Release','Remove'), value='Suspend',
                description='Action:', disabled=False,
            )

        act_btn = ipywidgets.Button( description='Apply' )
        act_btn.on_click(self.action)
        self.act_btn = [self.act_opt, act_btn]

    def f_act(self, job_desc):
        act = self.act_opt.value
        try:
            self._condor.job_action(act, job_desc)
        except Exception as err:
            self.log.error('Fail to apply action %s to job %s :\n\t%s',act, job_desc, err)
        else:
            self.log.info('Successfully %s job %s', act, job_desc)
        self.refresh()

    @property
    def root_widget(self):
        i=ipywidgets
        return i.VBox([i.HBox( [i.HBox(self.act_btn), self.refresh_btn  ] , layout=i.Layout(justify_content='flex-end') ),
                       self.grid_widget])

class TabPannel(object):
    _table_layout = tuple()
    def __init__(self):
        self.log = logging.Logger(__name__ + '.TabPannel')
        self.log.setLevel(logging.INFO)
        handler = LogHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s  - [%(levelname)s] %(message)s'))
        self.log.addHandler(handler)
        self.log_stack = handler.root_widget

    def tabs(self):
        _tabs = self._table_layout
        tabs = []
        for t , tab_factory in _tabs:
            tabs.append(tab_factory())
        tab = ipywidgets.Tab(children=tabs)
        for i, t_f in enumerate(_tabs):
            tab.set_title(i, t_f[0])
        return tab

    def dashboard(self):
        c = getattr(self,'main_ui_pannel', None)
        if not c:
            c = self.tabs()
            self.main_ui_pannel = c

        display(ipywidgets.VBox([c, self.log_stack]))



class Condor(TabPannel):
    def __init__(self, schedd_name=None):
        super().__init__()
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
            raise ValueError("This notebook is running in a condor job, which cannot kill itself!")
        act_args = ' && '.join([ '{}=={}'.format(k,v)  for k,v in job_argv.items() ])
        res = self.schedd.act( getattr(htcondor.JobAction, act), act_args )
        if not res['TotalSuccess'] > 0:
            trimedres = {k:res[k] for k in res if res[k]>0}
            raise RuntimeError("Action %s failed with error:%s"%(act, trimedres))
        self.log.info("The job [%s] has been %sed", job_argv, act )
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
        return JobView(self._wrap_tab_hdl(self.jobs,constraint, columns, index), self, log=self.log).root_widget

    def slot_table(self, constraint='',
             columns=['Machine','SlotID','Activity','CPUs','Memory'],
             index=['Machine','SlotID']):
        return TabView(self._wrap_tab_hdl(self.machines,constraint, columns, index), log=self.log).root_widget


    def machine_table(self,constraint='SlotID==1||SlotID=="1_1"',
            columns=['Machine','TotalSlots','TotalCPUs','TotalMemory',
                     'TotalDisk','TotalLoadAvg'],
            index=['Machine']):
        return TabView(self._wrap_tab_hdl(self.machines,constraint, columns, index), log=self.log).root_widget

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
        logger.info('[%d]: %s \n\t%s', p.poll(), out, err)

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


class LogHandler(logging.Handler):
    expireIn=15

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_stack = ipywidgets.Output(layout  = { 'width': '95%', 'max-height': '160px'})
        self.clear_btn = ipywidgets.Button(description='Clear' , layout={'display':'none'})
        self.clear_btn.on_click(self.clear_all)
        self.records = []

    def emit(self, record):
        ctime = record.created
        self.records.insert(0, (ctime, self.format(record)))
        now = time.time()
        outputs = tuple({
                'name': 'stdout',
                'output_type': 'stream',
                'text': r+'\n'
            } for c, r in self.records if now - c < self.expireIn
        )
        self.clear_btn.layout.display = 'block' if outputs else 'none'
        self.log_stack.outputs = outputs

    def clear_all(self, *args):
        self.records = []
        self.log_stack.clear_output()
        self.clear_btn.layout.display = 'none'

    @property
    def root_widget(self):
        return ipywidgets.VBox([self.log_stack, self.clear_btn])
