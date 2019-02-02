# Copyright 2019 Mingxuan Lin
# Copyright 2019 Lukas Koschmieder

from .Condor import CondorMagics, Condor
from .AixViPMaP import AixViPMaP, AixVPMagic

try:
    ip = get_ipython()
    ip.register_magics(AixVPMagic)
except:
    pass
