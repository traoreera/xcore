from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Loading(Component):
    """Composant Loading DaisyUI"""

    def render(self):
        return self.__render(
            type=self.props.get("type", "spinner"),
            size=self.props.get("size", "md"),
            color=self.props.get("color"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        type: Literal["spinner", "dots", "ring", "ball", "bars", "infinity"] = "spinner",
        size: Literal["xs", "sm", "md", "lg"] = "md",
        color: Optional[str] = None,
        classes: str = "",
    ) -> Markup:
        css_classes = ["loading", f"loading-{type}", f"loading-{size}"]
        if color:
            css_classes.append(f"text-{color}")

        return Markup(f'<span class="{" ".join(css_classes)} {classes}"></span>')
