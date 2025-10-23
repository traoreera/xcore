import uuid


def make_uid():
    return str(uuid.uuid4())[:30]
