
from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Swap(Component):
    """Composant Swap pour icônes toggle"""

    def render(self):
        return self.__render(
            on_icon=self.props.get("on_icon", ""),
            off_icon=self.props.get("off_icon", ""),
            rotate=self.props.get("rotate", False),
            flip=self.props.get("flip", False),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        on_icon: str, off_icon: str, rotate: bool = False, flip: bool = False, classes: str = ""
    ) -> Markup:
        effect = "swap-rotate" if rotate else ("swap-flip" if flip else "")

        return Markup(
            f"""
        <label class="swap {effect} {classes}">
            <input type="checkbox" />
            <div class="swap-on">{on_icon}</div>
            <div class="swap-off">{off_icon}</div>
        </label>
        """
        )
