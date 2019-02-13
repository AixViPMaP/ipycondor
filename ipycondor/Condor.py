# Copyright 2019 Mingxuan Lin
# Copyright 2019 Lukas Koschmieder

import os, time, logging, re, datetime
from subprocess import Popen, PIPE

import htcondor

from zmq.eventloop import ioloop

from IPython.core.magic import (Magics, magics_class, line_magic, cell_magic)
from IPython.display import display

import ipywidgets

from .ClassAdParser import QueryParser
from .ipcluster import NbIPClusterStart

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
logger.addHandler(ch)

try:
    import pandas as pd
    import numpy as np
    import qgrid
except ImportError as ierr:
    logger.warning('Cannot import %s\nSome functions may fail',ierr)

def my_job_id():
    p = re.compile(r'ClusterId\s+=\s+(\d+)\n')
    try:
        cladname = os.environ['_CONDOR_JOB_AD']
        with open(cladname,'r') as f:
            for line in f:
                m = p.match(line)
                if m:
                    return int(m.group(1))
            logger.error('Failed to find ClusterId attribute in file "%s"', cladname)
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
    return data if len(data)>0 else None

def lHBox (x):
    return ipywidgets.HBox(x, layout={'justify_content':'flex-end'} )

class TabView(object):
    refresh_timer = None
    def __init__(self, f, log=logger):
        self.f   = f
        self.log = log
        self.grid_widget = qgrid.show_grid(f(),show_toolbar=False,
                                    grid_options={'editable':False,
                                                  'minVisibleRows':10,
                                                  'maxVisibleRows':8})

        refresh_btn = ipywidgets.ToggleButton(
            value=False, description='Refresh', disabled=False,
            button_style='', # 'success', 'info', 'warning', 'danger' or ''
            tooltip='Auto refresh', icon='refresh'
        )
        refresh_btn.observe(self.refresh_btn_handler)
        self.refresh_btn=refresh_btn

        self.updated_at = ipywidgets.HTML( value='<i>%s</i>' % datetime.datetime.now(),
          description='Updated at')

    def refresh_btn_handler(self, evt):
        btn = evt.owner
        if not evt.type == 'change':
            return
        try:
            assert isinstance(btn, ipywidgets.ToggleButton), 'Illegal usage of refresh_btn_handler'
            if btn.value:
                if self.refresh_timer is None:
                    self.refresh_timer = ioloop.PeriodicCallback(self.refresh, 2000)
                self.refresh_timer.start()
            elif self.refresh_timer:
                self.refresh_timer.stop()
        except Exception as err:
            self.log.error('Failed switch on/off auto refresh because of %s', repr(err))

    def refresh(self, evt=None):
        try:
            self.updated_at.value = '<i>%s</i>' % datetime.datetime.now()
            df0 = self.grid_widget.df
            df  = self.f()
            if not np.array_equal(df0,df):
                self.grid_widget.df = df
                self.log.debug('Updating %s', type(self))
        except Exception as err:
            self.log.error('Failed to refresh because of %s', repr(err))

    def action(self, btn=None):
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
        return i.VBox([lHBox( [self.refresh_btn] ), self.grid_widget,self.updated_at])

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
            self.log.error('Failed to apply action %s to job %s :\n\t%s',act, job_desc, err)
        else:
            self.log.info('Successfully %s job %s', act, job_desc)
        self.refresh()

    @property
    def root_widget(self):
        i=ipywidgets
        return i.VBox([lHBox([i.HBox(self.act_btn), self.refresh_btn  ]),
                       self.grid_widget,self.updated_at])


class IpyclusterView(TabView):
    def __init__(self, f, cdr, **argv):
        super().__init__(f,**argv)
        self._condor = cdr

        self.exec_host_opt = ipywidgets.Dropdown(
                options=tuple(set(m['Machine'] for m in cdr.machines())),
                description='Remote host', disabled=False,
            )
        self.profile_opt = ipywidgets.Dropdown(
                options=self.list_profiles(),
                description='Profile', disabled=False,
            )
        self.n_opt = ipywidgets.IntText(2, description='No. engines',
            layout={'width':'200px'})

        self.act_btn = ipywidgets.Button( description='Start' )
        self.act_btn.on_click(self.start)

        self.stop_btn = ipywidgets.Button( description='Stop' )
        self.stop_btn.on_click(self.stop)

    def f_act(self, row_index):
        pass

    def start(self, btn):
        try:
            self._condor.start_ipcluster(self.profile_opt.value, self.n_opt.value, self.exec_host_opt.value)
        except Exception as err:
            self.log.error('Failed to start ipycluster with profile=%s because %s',self.profile_opt.value, err)

    def stop(self, btn):
        try:
            self._condor.ipyclusters[self.profile_opt.value].stop_launchers()
        except (KeyError, RuntimeError) as err:
            self.log.error('Failed to shutdown the cluster because %s', err)

    def list_profiles(self):
        try:
            from IPython.paths import get_ipython_dir
            from IPython.core.profileapp import list_profiles_in
        except ImportError as e:
            self.log.info("IPython not available: %s", e)
            return ['default',]
        return list_profiles_in(get_ipython_dir())

    @property
    def root_widget(self):
        i=ipywidgets
        return i.VBox([lHBox( [ self.profile_opt, self.exec_host_opt,self.n_opt, self.refresh_btn]  ),
                       lHBox([self.act_btn, self.stop_btn]), self.grid_widget, self.updated_at])

class TabPannel(object):
    _table_layout = tuple()
    main_ui_pannel= None
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
            self.main_ui_pannel = c = self.tabs()
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
        self._table_layout = [("Jobs", self.job_table),
            ("Machines", self.machine_table),
            ("IPyCluster", self.ipycluster_table)]
        self.my_job_id = my_job_id()
        self.ipyclusters = {}

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

    def start_ipcluster(self, profile, n, exec_host):
        # Mimic: https://github.com/ipython/ipyparallel/blob/master/ipyparallel/nbextension/clustermanager.py
        clusters = self.ipyclusters
        starter  = clusters.get(profile,None)
        if isinstance(starter, NbIPClusterStart):
            if (starter.engine_launcher.running or
                starter.controller_launcher.running):
                self.log.warning('Cluster for profile %s is already running!', profile)
                return
        # Always create new starter because IPClusterApp is designed for CLI use case
        clusters[profile] = starter = NbIPClusterStart(log=self.log)
        starter.initialize(['--profile', profile, '--cluster-id', 'UI'])
        self.log.info('Profile is loaded from %s with cluster-id=%s',
                       starter.profile_dir.location, starter.cluster_id)

        starter.engine_launcher.requirements = 'requirements = ( Machine == "%s" )' % exec_host
        starter.start(int(n))

    @staticmethod
    def _wrap_tab_hdl(classAds_hdl, constraint, cols, key_cols = tuple() ):
        columns = tuple(key_cols) + tuple(c for c in cols if c not in key_cols)
        # Create QGrid table widget
        def getdf():
            indx = key_cols
            df = pd.DataFrame(deep_parse(classAds_hdl(constraint), columns), columns=columns)
            if len(df)==0:
                indx = [indx[0],]
            if indx:
                df.set_index(list(indx),inplace=True)
                df.sort_index(inplace=True)
            return df
        return getdf

    def job_table(self, constraint='',
             columns = ('ClusterID','ProcID','Owner','JobStatus','JobDescription',
                      'JobStartDate','JobUniverse', 'RemoteHost'),
             index = ('ClusterID','ProcID')):
        return JobView(self._wrap_tab_hdl(self.jobs,constraint, columns, index), self, log=self.log).root_widget

    def slot_table(self, constraint='',
             columns = ('Machine','SlotID','Activity','CPUs','Memory'),
             index = ('Machine','SlotID')):
        return TabView(self._wrap_tab_hdl(self.machines,constraint, columns, index), log=self.log).root_widget


    def machine_table(self,constraint='SlotID==1||SlotID=="1_1"',
            columns = ('Machine','TotalSlots','TotalCPUs','TotalMemory',
                     'TotalDisk','TotalLoadAvg'),
            index = ('Machine',)):
        return TabView(self._wrap_tab_hdl(self.machines,constraint, columns, index), log=self.log).root_widget

    def ipycluster_table(self, constraint='ipengine_n > 0',
             columns = ('ClusterID','ProcID','Owner','JobStatus',
                      'JobStartDate','ipengine_n', 'RemoteHost'),
             index = ('ClusterID','ProcID')):
        return IpyclusterView(self._wrap_tab_hdl(self.jobs,constraint, columns, index), self, log=self.log).root_widget

@magics_class
class CondorMagics(Magics):
    _condor = None
    @cell_magic
    def CondorJob(self, line, cell): #pylint: disable=W0201
        "Creation of a condor job"
        # username = os.environ.get('JUPYTERHUB_USER', os.environ.get('USER'))
        p = Popen( [ 'condor_submit' ] , stdin=PIPE,stdout=PIPE, stderr=PIPE)
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
