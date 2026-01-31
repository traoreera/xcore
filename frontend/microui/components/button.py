from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Button(Component):
    """Composant Button DaisyUI"""

    def render(self):
        return self.__render(
            text=self.props.get("text", self.children or ""),
            variant=self.props.get("variant", "primary"),
            size=self.props.get("size", "md"),
            outline=self.props.get("outline", False),
            wide=self.props.get("wide", False),
            block=self.props.get("block", False),
            loading=self.props.get("loading", False),
            disabled=self.props.get("disabled", False),
            hx_get=self.props.get("hx_get"),
            hx_post=self.props.get("hx_post"),
            hx_target=self.props.get("hx_target"),
            hx_swap=self.props.get("hx_swap"),
            onclick=self.props.get("onclick"),
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
            "link",
            "info",
            "success",
            "warning",
            "error",
            "neutral",
            "outline",
        ] = "primary",
        size: Literal["xs", "sm", "md", "lg"] = "md",
        outline: bool = False,
        wide: bool = False,
        block: bool = False,
        loading: bool = False,
        disabled: bool = False,
        hx_get: Optional[str] = None,
        hx_post: Optional[str] = None,
        hx_target: Optional[str] = None,
        hx_swap: Optional[str] = None,
        onclick: Optional[str] = None,
        classes: str = "",
    ) -> Markup:
        css_classes = ["btn", f"btn-{variant}", f"btn-{size}"]

        if outline:
            css_classes.append(f"btn-outline")
        if wide:
            css_classes.append("btn-wide")
        if block:
            css_classes.append("btn-block")
        if loading:
            css_classes.append("loading")

        attrs = []
        if hx_get:
            attrs.append(f'hx-get="{hx_get}"')
        if hx_post:
            attrs.append(f'hx-post="{hx_post}"')
        if hx_target:
            attrs.append(f'hx-target="{hx_target}"')
        if hx_swap:
            attrs.append(f'hx-swap="{hx_swap}"')
        if onclick:
            attrs.append(f'onclick="{onclick}"')
        if disabled:
            attrs.append("disabled")

        all_classes = " ".join(css_classes + [classes])
        all_attrs = " ".join(attrs)

        return Markup(f'<button class="{all_classes}" {all_attrs}>{text}</button>')
