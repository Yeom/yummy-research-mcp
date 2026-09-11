"""Local service settings. Never serialize credentials into tool results."""
import os
from pathlib import Path

def setting(key,default=''):
    value=os.environ.get(key)
    if value:return value
    path=Path(__file__).resolve().parents[2]/'.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name,value=line.split('=',1)
                if name.strip()==key:return value.strip().strip('"').strip("'") or default
    return default
