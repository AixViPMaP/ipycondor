# Copyright 2019 Lukas Koschmieder, Mingxuan Lin

from .Condor import Condor, htcondor, TabView
import re

class AixViPMaP(Condor):
    def __init__(self, *args):
        super().__init__(*args)
        self._table_layout = [("Jobs", self.job_table),
                              ("Machines", self.machine_table),
                              ("Apps", self.app_table)]
    def apps(self, constraint=None):
        # the argument `constrain` is ignored
        machines = self.coll.query(htcondor.AdTypes.Startd, constraint='SlotID==1')
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
        col_N_ind=()
        return TabView(self._wrap_tab_hdl(
            self.apps, None,
            ['App', 'Version', 'Machine'],
            ['App', 'Version'])).root_widget
