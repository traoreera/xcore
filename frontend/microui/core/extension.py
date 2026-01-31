# microui/core/extension.py
class Component:
    """Base class for all UI components."""

    def __init__(self):
        self.props = {}
        self.children = None

    def render(self):
        raise NotImplementedError("Each component must implement its own render method.")
