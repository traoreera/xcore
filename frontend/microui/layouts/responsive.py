
from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register

from .desktop import DesktopLayout
from .mobile import MobileLayout


@register
class ResponsiveLayout(Component):
    """
    A responsive layout that renders a different layout based on the device type.
    """

    def render(self):
        device = self.props.get("device", "desktop")  # Default to desktop
        if device == "mobile":
            return MobileLayout.render(**self.props)
        else:
            return DesktopLayout.render(**self.props)
