from typing import List, Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Radio(Component):
    """Composant Radio Button DaisyUI"""

    def render(self):
        return self.__render(
            name=self.props.get("name", ""),
            options=self.props.get("options", []),
            selected_value=self.props.get("selected_value"),
            disabled=self.props.get("disabled", False),
            variant=self.props.get("variant", "primary"),
            size=self.props.get("size", "md"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        name: str,
        options: List[dict],
        selected_value: Optional[str] = None,
        disabled: bool = False,
        variant: Literal["primary", "secondary", "accent"] = "primary",
        size: Literal["xs", "sm", "md", "lg"] = "md",
        classes: str = "",
    ) -> Markup:
        css_classes = ["radio", f"radio-{variant}", f"radio-{size}"]
        disabled_attr = "disabled" if disabled else ""

        options_html = []
        for option in options:
            label = option.get("label", "")
            value = option.get("value", "")
            checked_attr = "checked" if value == selected_value else ""
            options_html.append(
                f"""
            <div class="form-control">
                <label class="label cursor-pointer">
                    <span class="label-text">{label}</span>
                    <input type="radio" name="{name}" value="{value}" class="{' '.join(css_classes)}" {checked_attr} {disabled_attr} />
                </label>
            </div>
            """
            )

        return Markup(f"""<div class="{classes}">{''.join(options_html)}</div>""")
