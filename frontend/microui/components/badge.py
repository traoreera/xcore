from typing import Literal

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Badge(Component):
    """Composant Badge DaisyUI"""

    def render(self):
        return self.__render(
            text=self.props.get("text", self.children or ""),
            variant=self.props.get("variant", "neutral"),
            size=self.props.get("size", "md"),
            outline=self.props.get("outline", False),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        text: str,
        variant: Literal[
            "primary",
            "secondary",
            "accent",
            "ghost",
            "info",
            "success",
            "warning",
            "error",
            "neutral",
        ] = "neutral",
        size: Literal["xs", "sm", "md", "lg"] = "md",
        outline: bool = False,
        classes: str = "",
    ) -> Markup:
        css_classes = ["badge", f"badge-{variant}", f"badge-{size}"]
        if outline:
            css_classes.append("badge-outline")
        if isinstance(text, (dict)):
            text = text.get("in_stock","badge")
        return Markup(f'<div class="{" ".join(css_classes)} {classes}">{text}</div>')
