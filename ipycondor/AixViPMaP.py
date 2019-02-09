# Copyright 2019 Lukas Koschmieder, Mingxuan Lin

from .Condor import Condor, htcondor, TabView, CondorMagics
import re


class AixViPMaP(Condor):
    def __init__(self, *args):
        super().__init__(*args)
        self._table_layout += [("Apps", self.app_table),]
    def apps(self, constraint=None):
        " Get APP info from `APP_*` attributes of all machines "
        # the argument `constrain` is ignored
        constraint='SlotID==1||SlotID=="1_1"'
        machines = self.coll.query(htcondor.AdTypes.Startd, constraint=constraint)
        apps = []
        for machine in machines:
            for keyword in machine:
                app = re.compile("APP_(.*)_VER_(.*)").match(keyword)
                if app and len(app.groups()) == 2:
                    apps.append((app.groups()[0].replace('_', ' '),
                                 app.groups()[1].replace('_', '.'),
                                 machine['Machine']))
        return [ dict(zip(['App', 'Version', 'Machine'], a)) for a in set(apps) ]

    def app_table(self):
        " Table for APPs "
        return TabView(self._wrap_tab_hdl(
            self.apps, None,
            ['App', 'Version', 'Machine'],
            ['App', 'Version']), log=self.log).root_widget

class AixVPMagic(CondorMagics):
    @property
    def condor(self):
        c = getattr(self,'_condor', None)
        if not isinstance(c, Condor):
            c = AixViPMaP()
            self._condor = c
        return c
