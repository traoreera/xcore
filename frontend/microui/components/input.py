from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Input(Component):
    """Composant Input DaisyUI"""

    def render(self):
        return self.__render(
            name=self.props.get("name", ""),
            type=self.props.get("type", "text"),
            placeholder=self.props.get("placeholder", ""),
            value=self.props.get("value", ""),
            label=self.props.get("label"),
            size=self.props.get("size", "md"),
            bordered=self.props.get("bordered", True),
            error=self.props.get("error"),
            hx_post=self.props.get("hx_post"),
            hx_trigger=self.props.get("hx_trigger"),
            hx_target=self.props.get("hx_target"),
            required=self.props.get("required", True),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        name: str,
        type: str = "text",
        placeholder: str = "",
        value: str = "",
        label: Optional[str] = None,
        size: Literal["xs", "sm", "md", "lg"] = "md",
        bordered: bool = True,
        error: Optional[str] = None,
        hx_post: Optional[str] = None,
        hx_trigger: Optional[str] = None,
        hx_target: Optional[str] = None,
        required: bool = True,
        classes: str = "",
    ) -> Markup:
        css_classes = ["input", f"input-{size}", "w-full"]
        if bordered:
            css_classes.append("input-bordered")
        if error:
            css_classes.append("input-error")

        attrs = []
        if hx_post:
            attrs.append(f'hx-post="{hx_post}"')
        if hx_trigger:
            attrs.append(f'hx-trigger="{hx_trigger}"')
        if hx_target:
            attrs.append(f'hx-target="{hx_target}"')

        label_html = (
            f'<label class="label"><span class="label-text">{label}</span></label>' if label else ""
        )
        error_html = (
            f'<label class="label"><span class="label-text-alt text-error">{error}</span></label>'
            if error
            else ""
        )
        all_attrs = " ".join(attrs)

        return Markup(
            f"""
        <div class="form-control {classes}">
            {label_html}
            <input type="{type}" name="{name}" placeholder="{placeholder}" value="{value}"  {"required" if required else ""} class="{' '.join(css_classes)}" {all_attrs} />
            {error_html}
        </div>
        """
        )
