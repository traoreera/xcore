import os
import json
import sys
from typing import Optional, Dict
from rich import print_json



class Configure:

    def __init__(self, file:str,):
        self.file = file

        with open(self.file, 'r') as f:
            self.cfg = json.load(f)
        
    def __call__(self,conf:str) -> Optional[Dict | Dict ]:
        if conf in self.cfg:
            return self.cfg[conf]
        elif conf=="All":
            return self.cfg




class CfgManager:
    
    def __init__(self,conf:Configure):
        self.conf = conf('manager')
        self.all = conf('All')
        self.file = conf.file


    def cfgplugins(self) -> Dict[str, Dict[str, str]] | None:
        if self.conf is None:
            return None
        return self.conf['plugins']

    def cfgtasks(self) -> Dict[str, Dict[str, str]] | None: 
        if self.conf is None:
            return None
        return self.conf['tasks']
    
    def cfgsnapshot(self) -> Dict[str, Dict[str, str]] | None: 
        if self.conf is None:
            return None
        return self.conf['snapshot']

    def dotenv(self) -> Dict[str, Dict[str, str]] | None: 
        if self.conf is None:
            return None
        return self.conf['dotenv']

    def cfglog(self) -> Dict[str, Dict[str, str]] | None: 
        if self.conf is None:
            return None
        return self.conf['log']

    def addcfg(self, key: str, value: str) -> None:
        if self.conf is None:
            self.conf = {}
        self.conf[key] = value

    def removecfg(self, key: str) -> None:
        if self.conf is None: return
        if key in self.conf:
            del self.conf[key]
    

    def save(self):
        if self.all is None: return 
        self.all['manager'].update(self.conf)

        with open(self.file, 'w') as f:
            json.dump(self.all, f, indent=4)

    def print(self):
        print_json(data=self.conf)
    
    def get(self,module:str, key:str):

        if module == 'log':
            return self.cfglog()[key]
        
        elif module == 'plugins':
            return self.cfgplugins()[key]
        elif module == 'tasks':
            return self.cfgtasks()[key]

        elif module == 'snapshot':
            return self.cfgsnapshot()[key]


        
        return None

class Secure:

    def __init__(self,conf:Configure):
        self.conf = conf('secure')
        self.all = conf('All')
        self.file = conf.file
    

    def cfgPassword(self,) -> Dict[str, Dict[str, str]] | None:
        if self.conf is None:
            return None
        return self.conf['password']
    

    def dotenv(self,):
        if self.conf is None:
            return None
        return self.conf['dotenv']



    def save(self):
        if self.all is None: return 
        self.all['secure'].update(self.conf)

        with open(self.file, 'w') as f:
            json.dump(self.all, f, indent=4)
    

    def remove(self, key: str) -> None:
        if self.conf is None: return
        if key in self.conf:
            del self.conf[key]


    def get(self,module:str, key:str):

        if module == 'password':
            return self.cfgPassword()[key]
        return None 


class Migration:

    def __init__(self,conf:Configure):
        self.conf = conf('migration')
        self.all = conf('All')
        self.file = conf.file
    


    def cfgLogger(self,):
        if self.conf is None:
            return None
        return self.conf['logger']
    
    def cfgAutoMigration(self,):

        if self.conf is None:
            return None
        return self.conf['automigration']
    
    def cfgAutoDiscovery(self,):

        if self.conf is None:
            return None
        return self.conf['model_discovery']


    def get(self, module, key):
        if module == 'log':
            return self.cfgLogger()[key]
        
        if module == "automigration":
            return self.cfgAutoMigration()[key]
        
        if module =="discovery":
            return self.cfgAutoDiscovery()[key]

        else:
            return self.conf[key]
        return None