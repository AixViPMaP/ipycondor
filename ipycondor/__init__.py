# Copyright 2019 Mingxuan Lin

from .Condor import CondorMagics, Condor

try:
    ip = get_ipython()
    ip.register_magics(CondorMagics)
except:
    pass
