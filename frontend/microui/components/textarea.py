from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Textarea(Component):
    """Composant Textarea DaisyUI"""

    def render(self):
        return self.__render(
            name=self.props.get("name", ""),
            placeholder=self.props.get("placeholder", ""),
            value=self.props.get("value", ""),
            label=self.props.get("label"),
            bordered=self.props.get("bordered", True),
            disabled=self.props.get("disabled", False),
            variant=self.props.get("variant", "primary"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        name: str,
        placeholder: str = "",
        value: str = "",
        label: Optional[str] = None,
        bordered: bool = True,
        disabled: bool = False,
        variant: Literal[
            "primary", "secondary", "accent", "info", "success", "warning", "error"
        ] = "primary",
        classes: str = "",
    ) -> Markup:
        css_classes = ["textarea", f"textarea-{variant}", "w-full"]
        if bordered:
            css_classes.append("textarea-bordered")
        disabled_attr = "disabled" if disabled else ""

        label_html = (
            f'<label class="label"><span class="label-text">{label}</span></label>' if label else ""
        )

        return Markup(
            f"""
        <div class="form-control {classes}">
            {label_html}
            <textarea name="{name}" class="{' '.join(css_classes)}" placeholder="{placeholder}" {disabled_attr}>{value}</textarea>
        </div>
        """
        )
