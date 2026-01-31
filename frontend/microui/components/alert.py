from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Alert(Component):
    """Composant Alert DaisyUI"""

    def render(self):
        return self.__render(
            message=self.props.get("message", self.children or ""),
            type=self.props.get("type", "info"),
            dismissible=self.props.get("dismissible", False),
            icon=self.props.get("icon", None),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        message: str,
        type: Literal["info", "success", "warning", "error"] = "info",
        dismissible: bool = False,
        icon: Optional[str] = None,
        classes: str = "",
    ) -> Markup:
        icons = {
            "info": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-info shrink-0 w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
            "success": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-success shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
            "warning": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-warning shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>',
            "error": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-error shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
        }

        icon_html = icon or icons.get(type, "")
        dismiss_html = (
            '<button class="btn btn-sm btn-circle btn-ghost" onclick="this.parentElement.remove()">✕</button>'
            if dismissible
            else ""
        )

        return Markup(
            f"""
        <div role="alert" class="alert alert-{type} {classes}">
            {icon_html}
            <span>{message}</span>
            {dismiss_html}
        </div>
        """
        )


    @staticmethod
    def rendering(        message: str,
        type: Literal["info", "success", "warning", "error"] = "info",
        dismissible: bool = False,
        icon: Optional[str] = None,
        classes: str = "",)-> Markup:
            return Alert.__render(
                message=message,
                type=type,
                dismissible=dismissible,
                icon=icon,
                classes=classes,
            )