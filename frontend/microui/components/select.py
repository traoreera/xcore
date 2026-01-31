from typing import List, Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Select(Component):
    """Composant Select DaisyUI"""

    def render(self):
        return self.__render(
            name=self.props.get("name", ""),
            options=self.props.get("options", []),
            label=self.props.get("label"),
            selected_value=self.props.get("selected_value"),
            disabled=self.props.get("disabled", False),
            variant=self.props.get("variant", "primary"),
            size=self.props.get("size", "md"),
            bordered=self.props.get("bordered", True),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        name: str,
        options: List[dict],
        label: Optional[str] = None,
        selected_value: Optional[str] = None,
        disabled: bool = False,
        variant: Literal[
            "primary", "secondary", "accent", "info", "success", "warning", "error"
        ] = "primary",
        size: Literal["xs", "sm", "md", "lg"] = "md",
        bordered: bool = True,
        classes: str = "",
    ) -> Markup:
        css_classes = ["select", f"select-{variant}", f"select-{size}", "w-full"]
        if bordered:
            css_classes.append("select-bordered")
        disabled_attr = "disabled" if disabled else ""

        options_html = []
        for option in options:
            label = option.get("label", "")
            value = option.get("value", "")
            selected_attr = "selected" if value == selected_value else ""
            options_html.append(f'<option value="{value}" {selected_attr}>{label}</option>')

        label_html = (
            f'<label class="label"><span class="label-text">{label}</span></label>' if label else ""
        )

        return Markup(
            f"""
        <div class="form-control {classes}">
            {label_html}
            <select name="{name}" class="{' '.join(css_classes)}" {disabled_attr}>
                {''.join(options_html)}
            </select>
        </div>
        """
        )
