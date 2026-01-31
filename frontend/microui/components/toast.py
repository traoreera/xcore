from typing import Literal

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Toast(Component):
    """Composant Toast pour notifications"""

    def render(self):
        return self.__render(
            message=self.props.get("message", ""),
            type=self.props.get("type", "info"),
            position=self.props.get("position", "top-end"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        message: str,
        type: Literal["info", "success", "warning", "error"] = "info",
        position: Literal[
            "top-start",
            "top-center",
            "top-end",
            "middle-start",
            "middle-center",
            "middle-end",
            "bottom-start",
            "bottom-center",
            "bottom-end",
        ] = "top-end",
        classes: str = "",
    ) -> Markup:
        position_map = {
            "top-start": "toast-top toast-start",
            "top-center": "toast-top toast-center",
            "top-end": "toast-top toast-end",
            "middle-start": "toast-middle toast-start",
            "middle-center": "toast-middle toast-center",
            "middle-end": "toast-middle toast-end",
            "bottom-start": "toast-bottom toast-start",
            "bottom-center": "toast-bottom toast-center",
            "bottom-end": "toast-bottom toast-end",
        }

        return Markup(
            f"""
        <div class="toast {position_map.get(position, 'toast-top toast-end')} {classes}">
            <div class="alert alert-{type}">
                <span>{message}</span>
            </div>
        </div>
        """
        )
