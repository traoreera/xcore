from typing import Dict, List

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Timeline(Component):
    """Composant Timeline"""

    def render(self):
        return self.__render(
            items=self.props.get("items", []),
            compact=self.props.get("compact", False),
            snap=self.props.get("snap", False),
            vertical=self.props.get("vertical", True),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        items: List[Dict],
        compact: bool = False,
        snap: bool = False,
        vertical: bool = True,
        classes: str = "",
    ) -> Markup:
        timeline_classes = ["timeline"]
        if compact:
            timeline_classes.append("timeline-compact")
        if snap:
            timeline_classes.append("timeline-snap-icon")
        if vertical:
            timeline_classes.append("timeline-vertical")
        else:
            timeline_classes.append("timeline-horizontal")

        items_html = []
        for i, item in enumerate(items):
            icon = item.get("icon", f'<div class="text-xl">{i+1}</div>')
            position = "timeline-start" if i % 2 == 0 else "timeline-end"

            items_html.append(
                f"""
            <li>
                <div class="timeline-middle">{icon}</div>
                <div class="{position} timeline-box">
                    {item.get("title") and f'<div class="font-bold">{item["title"]}</div>' or ''}
                    {item.get("content", "")}
                    {item.get("date") and f'<div class="text-xs text-gray-500 mt-2">{item["date"]}</div>' or ''}
                </div>
                <hr />
            </li>
            """
            )

        return Markup(
            f"""
        <ul class="{' '.join(timeline_classes)} {classes}">
            {''.join(items_html)}
        </ul>
        """
        )
