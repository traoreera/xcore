from typing import Literal

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Checkbox(Component):
    """Composant Checkbox DaisyUI"""

    def render(self):
        return self.__render(
            name=self.props.get("name", ""),
            label=self.props.get("label", ""),
            checked=self.props.get("checked", False),
            disabled=self.props.get("disabled", False),
            variant=self.props.get("variant", "primary"),
            size=self.props.get("size", "md"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        name: str,
        label: str,
        checked: bool = False,
        disabled: bool = False,
        variant: Literal["primary", "secondary", "accent"] = "primary",
        size: Literal["xs", "sm", "md", "lg"] = "md",
        classes: str = "",
    ) -> Markup:
        css_classes = ["checkbox", f"checkbox-{variant}", f"checkbox-{size}"]
        checked_attr = "checked" if checked else ""
        disabled_attr = "disabled" if disabled else ""

        return Markup(
            f"""
        <div class="form-control {classes}">
            <label class="label cursor-pointer">
                <span class="label-text">{label}</span>
                <input type="checkbox" name="{name}" class="{' '.join(css_classes)}" {checked_attr} {disabled_attr} />
            </label>
        </div>
        """
        )
