from typing import Literal

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Skeleton(Component):
    """Composant Skeleton pour loading states"""

    def render(self):
        return self.__render(
            type=self.props.get("type", "text"),
            lines=self.props.get("lines", 3),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        type: Literal["text", "avatar", "card", "custom"] = "text",
        lines: int = 3,
        classes: str = "",
    ) -> Markup:
        if type == "avatar":
            return Markup(
                f"""
            <div class="flex items-center gap-4 {classes}">
                <div class="skeleton w-16 h-16 rounded-full shrink-0"></div>
                <div class="flex flex-col gap-4 flex-1">
                    <div class="skeleton h-4 w-full"></div>
                    <div class="skeleton h-4 w-3/4"></div>
                </div>
            </div>
            """
            )

        elif type == "card":
            return Markup(
                f"""
            <div class="flex flex-col gap-4 {classes}">
                <div class="skeleton h-32 w-full"></div>
                <div class="skeleton h-4 w-full"></div>
                <div class="skeleton h-4 w-3/4"></div>
            </div>
            """
            )

        else:  # text
            lines_html = "".join(
                [
                    f'<div class="skeleton h-4 w-{"full" if i == 0 else "3/4" if i == lines-1 else "full"}"></div>'
                    for i in range(lines)
                ]
            )
            return Markup(
                f"""
            <div class="flex flex-col gap-4 {classes}">
                {lines_html}
            </div>
            """
            )
