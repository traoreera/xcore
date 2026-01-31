from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Progress(Component):
    """Composant Progress Bar"""

    def render(self):
        return self.__render(
            value=self.props.get("value", 0),
            max=self.props.get("max", 100),
            color=self.props.get("color"),
            size=self.props.get("size", "md"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        value: int,
        max: int = 100,
        color: Optional[str] = None,
        size: Literal["xs", "sm", "md", "lg"] = "md",
        classes: str = "",
    ) -> Markup:
        color_class = f"progress-{color}" if color else ""
        size_class = f"progress-{size}" if size != "md" else ""

        return Markup(
            f"""
        <progress class="progress {color_class} {size_class} {classes}"
                  value="{value}" max="{max}"></progress>
        """
        )
