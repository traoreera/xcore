import uuid

from xcore.appcfg import xcfg


def make_ids():
    return str(uuid.uuid4())[:30]
