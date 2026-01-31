from typing import Dict, List

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Collapse(Component):
    """Composant Collapse (Accordion)"""

    def render(self):
        return self.__render(
            items=self.props.get("items", []),
            arrow=self.props.get("arrow", True),
            plus=self.props.get("plus", False),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        items: List[Dict], arrow: bool = True, plus: bool = False, classes: str = ""
    ) -> Markup:
        icon_class = "collapse-arrow" if arrow else ("collapse-plus" if plus else "collapse-close")

        collapses = []
        for i, item in enumerate(items):
            open_attr = "checked" if item.get("open", False) else ""

            collapses.append(
                f"""
            <div class="collapse {icon_class} bg-base-200 mb-2">
                <input type="radio" name="collapse-{id(items)}" {open_attr} />
                <div class="collapse-title text-xl font-medium">
                    {item.get("title", "")}
                </div>
                <div class="collapse-content">
                    {item.get("content", "")}
                </div>
            </div>
            """
            )

        return Markup(
            f"""
        <div class="{classes}">
            {''.join(collapses)}
        </div>
        """
        )
