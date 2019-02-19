*********
ipycondor
*********

``ipycondor`` provides ``IPython`` interfaces for `HTCondor <https://research.cs.wisc.edu/htcondor/index.html>`_ and its native python bindings. 
Users can submit, monitor and manage condor jobs with a graphical user interface (GUI) backed by `ipywidgets <https://github.com/jupyter-widgets/ipywidgets>`_. It also support the creation of a `ipyparallel <https://github.com/ipython/ipyparallel>`_ cluster as a condor job running on remote execute nodes with SSH tunneling for communication between ipython engines and the controller.

Install
*******

With ``pip``
------------

.. code:: sh

    $ pip install git+https://github.com/gdlmx/ipycondor.git

Manually
--------

.. code:: sh

    $ git clone https://github.com/gdlmx/ipycondor.git
    $ cd ipycondor
    $ python setup.py install

Configuration
*************

The `IPython configuration files <https://ipython.org/ipython-doc/3/config/intro.html>`_ are typically located in directory at ``~/.ipython/profile_<name>``, where ``<name>`` is the canonical name of the profile. The config files involved in the following steps should be found/created inside this directory.

IPython
-------

To load the ipython magics ``%%CondorJob`` and ``%CondorMon`` at startup, insert the following line in the ipython config file ``ipython_config.py``.

.. code:: python

    c.InteractiveShellApp.extensions = ['ipycondor.Condor']


IPCluster
---------

To use the condor launcher for ``IPClusterEngines`` , the ipcluster profile should be manually configurated: 

1. Insert the following line into ``ip_cluster_config.py``

.. code:: python

    c.IPClusterEngines.engine_launcher_class = 'ipycondor.launcher.HTCondorEngineSetSshLauncher'
    c.IPClusterStart.controller_launcher_class = 'Local'

2. Create a shell script and save it as "ipengine_launcher". 

.. code:: bash
    
    source /opt/conda/bin/activate base
    exec "$@" 

This script will be used as the ``executable`` for the condor job to launch ``ipengines`` on the execute node, modify it according to the environments of your computer cluster.

Usage
*****

Please refer to the `example notebook <examples/ipycondor_usage.ipynb>`_ in the subdirectory "examples".
