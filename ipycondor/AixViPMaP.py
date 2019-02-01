# Copyright 2019 Lukas Koschmieder

from .Condor import *
import re

class AixViPMaP(Condor):
    @tab("Apps")
    def app_table(self):
        machines = self.coll.query(htcondor.AdTypes.Startd, constraint='SlotID==1')
        apps = []
        for machine in machines:
            for keyword in machine:
                app = re.compile("APP_(.*)_VER_(.*)").match(keyword)
                if app and len(app.groups()) == 2:
                        apps.append((app.groups()[0].replace('_', ' '),
                                     app.groups()[1].replace('_', '.'),
                                     machine['Machine']))
        return to_qgrid(data=list(set(apps)),
                        columns=['App', 'Version', 'Machine'],
                        index=['App', 'Version'])
