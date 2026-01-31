from typing import Dict, List, Literal

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Tabs(Component):
    """Composant Tabs"""

    def render(self):
        return self.__render(
            tabs=self.props.get("tabs", []),
            variant=self.props.get("variant", "bordered"),
            size=self.props.get("size", "md"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        tabs: List[Dict],
        variant: Literal["bordered", "lifted", "boxed"] = "bordered",
        size: Literal["xs", "sm", "md", "lg"] = "md",
        classes: str = "",
    ) -> Markup:
        tabs_html = []
        content_html = []

        for i, tab in enumerate(tabs):
            tab_id = tab.get("id", f"tab_{i}")
            active = "tab-active" if tab.get("active", False) else ""

            tabs_html.append(
                f"""
            <a class="tab tab-{size} {active}" onclick="document.querySelectorAll('.tab-content').forEach(t => t.classList.add('hidden'));
                        document.getElementById('{tab_id}_content').classList.remove('hidden');
                        document.querySelectorAll('.tab').forEach(t => t.classList.remove('tab-active'));
                        this.classList.add('tab-active');">
                {tab.get("text", "")}
            </a>
            """
            )

            content_display = "" if tab.get("active", False) else "hidden"
            content_html.append(
                f"""
            <div id="{tab_id}_content" class="tab-content {content_display} p-4">
                {tab.get("content", "")}
            </div>
            """
            )

        return Markup(
            f"""
        <div class="{classes}">
            <div role="tablist" class="tabs tabs-{variant}">
                {''.join(tabs_html)}
            </div>
            <div class="tab-container">
                {''.join(content_html)}
            </div>
        </div>
        """
        )
