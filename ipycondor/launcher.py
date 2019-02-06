# Copyright 2019 Mingxuan Lin

from ipyparallel.apps.launcher import HTCondorLauncher, BatchClusterAppMixin
from traitlets import (
    Any, Integer, CFloat, List, Unicode, Dict, Instance, HasTraits, CRegExp, TraitError, validate, default, observe
)

import htcondor, time, json, os, re, subprocess, ipyparallel, socket


class HTCondorEngineSetSshLauncher(HTCondorLauncher, BatchClusterAppMixin):
    """Launch Engines using HTCondor and use condor_ssh_to_job for port forwarding"""

    batch_file_name = Unicode('htcondor_engines.job', config=True)
    batch_template  = Unicode("""
universe             = vanilla
executable           = {exec_cmd}
transfer_executable  = true
transfer_input_files ={to_send}
should_transfer_files= yes

stream_output = true
stream_error  = true
output = ipyengine.$(ClusterId).$(ProcId).out.txt
error  = ipyengine.$(ClusterId).$(ProcId).err.txt
log    = ipyengine.$(ClusterId).$(ProcId).log

arguments = "mpiexec --n {n} ipengine --file={name_pre}-engine.json --cluster-id={cluster_id} --mpi --timeout=30 "

{requirements}
{environments}
{proxy}
+ipengine_starter_n={n}

queue
    """ , config=True)

    to_send      = List([], config=True, help="List of local files to send before starting")

    requirements = Unicode('', help='The requirements command in the job description file',config=True)
    environments = Unicode('', help='The environment command in the job description file', config=True)
    exec_cmd     = Unicode('ipengine_launcher',config=True)

    ssh_to_job_proc = Any()
    context_keys = Unicode('requirements,environments,exec_cmd,name_pre', config=True)

    @default('exec_cmd')
    def _exec_cmd_default(self):
        return os.path.join(self.profile_dir, 'ipengine_launcher')

    @validate('requirements', 'environments')
    def _valid_requirements(self,proposal):
        v = proposal['value']
        if v=='' or re.match('\s*\w+\s*=', v):
            return v
        raise TraitError('classad syntax error with %s'%v)

    @property
    def ipcontroller_info(self):
        return os.path.join(self.profile_dir, 'security', self.name_pre+'-engine.json' )

    @property
    def name_pre(self):
        return 'ipcontroller-%s' % self.cluster_id if self.cluster_id else 'ipcontroller'


    def start(self, n):

        prefix=lambda a,b: (a+b) if b else ''
        self.context['proxy'] = prefix( 'x509UserProxy=', os.environ.get('X509_USER_PROXY') )
        for k in self.context_keys.split(','):    self.context[k] = getattr(self,k)
        cl_info = self.ipcontroller_info
        to_send = [ cl_info ] + self.to_send
        self.context['to_send'] = ','.join( to_send )
        self.log.debug("Submitting condor job with context %s", self.context)

        assert wait_for_new_file(cl_info), "File not found or too old %s"%cl_info
        assert all([os.path.exists(x) for x in to_send]),'One or more input file(s) do not exist\n%s'%to_send

        # call parent method
        ans = super().start(n)

        # wait until the job is running
        jstatus=0
        for k in range(30):
            jstatus = self.poll()
            if jstatus == 2:
                break
            time.sleep(1)
        if not jstatus==2:
            err_msg='Condor job %s failed to start (JobStatus=%s)' % (self.job_id, jstatus)
            self.log.error(err_msg, exc_info=True)
            raise RuntimeError(err_msg)

        # start up a ssh tunnel
        remote_host = self.getjobattr('RemoteHost').split('@')[1]
        local_host  = socket.getfqdn()
        if remote_host.lower().find(local_host.lower())<0:
            self.create_tunnel()
        return ans

    def poll(self):
        try:
            return int(self.getjobattr('JobStatus'))
        except:
            return 0

    def getjobattr(self,attrname):
        val = subprocess.check_output(['condor_q', '-format','%s', attrname, str(self.job_id)])
        val = val.decode(errors='ignore')
        self.log.debug('Condor job %s: %s=%s ',self.job_id, attrname, val)
        return val

    def create_tunnel(self):
        with open(self.ipcontroller_info, 'r') as f:
            stat_engine=json.load( f )

        args=['condor_ssh_to_job', str(self.job_id), '-N']
        for k in ("registration", "control", "mux", "hb_ping", "hb_pong", "task", "iopub" ):
            args += ['-R', 'localhost:{0}:localhost:{0}'.format(stat_engine[k])]

        p=subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out,err=p.communicate(timeout=2)
            raise RuntimeError(out,err)
        except subprocess.TimeoutExpired:
            self.ssh_to_job_proc = p
        self.log.info('`condor_ssh_to_job` started (PID=%d)', p.pid)
        def stop_ssh_tunnel(r):
            out=''
            if p.poll() is None:
                p.terminate()
                out=p.communicate(timeout=1)
            self.log.info('`condor_ssh_to_job` %s exited with %s: %s',p.pid, p.poll(), out)

        self.on_stop(stop_ssh_tunnel) # register as a callback (triggered by `notify_stop`)

def wait_for_new_file(filename, timeout=20):
    for i in range(timeout):
        try:
            fileage = time.time() - os.stat(filename).st_mtime
            if ( fileage<timeout and fileage>0 ):
                return True
        except FileNotFoundError:
            time.sleep(1)
    return False

