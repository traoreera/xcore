from typing import Dict, List, Literal

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register

from .divider import Divider


@register
class Dropdown(Component):
    """Composant Dropdown"""

    def render(self):
        return self.__render(
            button_text=self.props.get("button_text", "Dropdown"),
            items=self.props.get("items", []),
            position=self.props.get("position", "dropdown-end"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        button_text: str,
        items: List[Dict],
        position: Literal[
            "dropdown-end", "dropdown-top", "dropdown-bottom", "dropdown-left", "dropdown-right"
        ] = "dropdown-end",
        classes: str = "",
    ) -> Markup:
        menu_items = []
        divider = ""
        for item in items:

            if item.get("divider"):

                divider = Divider.rendering(
                    text=item.get("text", ""),
                    vertical=item.get("position", "vertical") == "vertical",
                    color=item.get("color"),
                )

            menu_items.append(
                f"""
                <li>
                    <a href="{item.get("href", "#")}"
                        {'hx-get="' + item["hx_get"] + '"' if item.get("hx_get") else ''}>
                        {item.get("icon", "")} {item.get("text", "")}
                    </a>
                </li> 
                """
                if item.get("divider", False) is False
                else divider
            )

        return Markup(
            f"""
        <div class="dropdown {position} {classes}">
            <div tabindex="0" role="button" class="btn m-1">{button_text}</div>
            <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52">
                {''.join(menu_items)}
            </ul>
        </div>
        """
        )

    @staticmethod
    def rendering(
        button_text: str,
        items: List[Dict],
        position: Literal[
            "dropdown-end", "dropdown-top", "dropdown-bottom", "dropdown-left", "dropdown-right"
        ] = "dropdown-end",
        classes: str = "",
    ) -> Markup:
        """Static method to render Dropdown without instantiating the class."""
        return Dropdown.__render(button_text, items, position, classes)
