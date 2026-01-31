from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Tooltip(Component):
    """Composant Tooltip"""

    def render(self):
        return self.__render(
            content=self.props.get("content", self.children or ""),
            text=self.props.get("text", ""),
            position=self.props.get("position", "top"),
            color=self.props.get("color"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        content: str,
        text: str,
        position: Literal["top", "bottom", "left", "right"] = "top",
        color: Optional[str] = None,
        classes: str = "",
    ) -> Markup:
        color_class = f"tooltip-{color}" if color else ""

        return Markup(
            f"""
        <div class="tooltip tooltip-{position} {color_class} {classes}" data-tip="{text}">
            {content}
        </div>
        """
        )
