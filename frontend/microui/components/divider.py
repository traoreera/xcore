from typing import Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Divider(Component):
    """Composant Divider"""

    def render(self):
        return self.__render(
            text=self.props.get("text"),
            vertical=self.props.get("vertical", False),
            color=self.props.get("color"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        text: Optional[str] = None,
        vertical: bool = False,
        color: Optional[str] = None,
        classes: str = "",
    ) -> Markup:
        orientation = "divider-vertical" if vertical else "divider-horizontal"
        color_class = f"divider-{color}" if color else ""

        return Markup(
            f"""
        <div class="divider {orientation} {color_class} {classes}">
            {text or ""}
        </div>
        """
        )

    @staticmethod
    def rendering(text, vertical: bool = False, color: Optional[str] = None, classes: str = ""):
        return Divider.__render(text, vertical, color, classes)
