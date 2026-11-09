"""Existing H3/H5 disposable runtime, with H6's separately pinned host settings."""
import os,secrets
from pathlib import Path
from engineering.capacity.workload import Lab as Parent
from engineering.operations.configuration import profile,write

class OperationalLab(Parent):
    def __init__(self,*args):
        super().__init__(*args);self.metrics_key=secrets.token_urlsafe(32);self.profile_changes={};self.extra_environment={};self.bad_profile_pin=False;self.stall=3
    def start(self,*,workers=False,port=18081,pool=None):
        selected=34 if pool is None else pool
        cfg=profile(workers=workers,pool=selected,stall=self.stall);cfg.update(self.profile_changes)
        path=self.logs/('operational-'+str(self.sequence)+'.json');values=write(path,cfg);values['ACP_METRICS_READ_KEY']=self.metrics_key;values.update(self.extra_environment)
        if self.bad_profile_pin:values['ACP_OPERATIONAL_CONFIG_SHA256']='0'*64
        old={key:os.environ.get(key) for key in values}
        os.environ.update(values)
        try:return super().start(workers=workers,port=port,pool=selected)
        finally:
            for key,value in old.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
