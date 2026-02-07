from frontend.engine.component import ComponentRegistry


def register(cls):
    """
    A class decorator that registers the component in the ComponentRegistry.
    It registers an *instance* of the class.
    """
    if not hasattr(cls, "render"):
        raise TypeError(f"Component {cls.__name__} must have a render method.")
    ComponentRegistry.register(cls.__name__.lower(), cls())
    return cls
