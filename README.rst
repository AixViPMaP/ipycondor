*********
ipycondor
*********

IPython binding for HTCondor

Install
*******

.. code:: sh

    $ python setup.py install

Configuration
=============

IPython
-------

For using the ``IPython`` magics, please insert the following line in the ipython config file ``ipython_config.py``.

.. code:: python

    c.InteractiveShellApp.extensions = ['ipycondor.Condor']


IPCluster
---------

For using the ``IPClusterEngines`` launcher, the ipcluster profile should be manually configurated: 

1. Insert the following line into ``<your_profile_dir>/ip_cluster_config.py``

.. code:: python

    c.IPClusterEngines.engine_launcher_class = 'ipycondor.launcher.HTCondorEngineSetSshLauncher'

2. Create a shell script and save it to ``<your_profile_dir>/ipengine_launcher``. Since this script will be executed on a remote node, modify it according to the environments of your computer cluster.

.. code:: bash
    
    export CONDA_DIR=/opt/conda
    source "$CONDA_DIR/bin/activate"
    "$@" 

