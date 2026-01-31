from typing import Dict, List

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Stats(Component):
    """Composant Stats"""

    def render(self):
        return self.__render(
            stats=self.props.get("stats", []),
            vertical=self.props.get("vertical", False),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(stats: List[Dict], vertical: bool = False, classes: str = "") -> Markup:
        orientation = "stats-vertical" if vertical else "stats-horizontal"

        stats_html = []
        for stat in stats:
            icon = (
                f'<div class="stat-figure text-{stat.get("color", "primary")}">{stat.get("icon", "")}</div>'
                if stat.get("icon")
                else ""
            )

            stats_html.append(
                f"""
            <div class="stat">
                {icon}
                <div class="stat-title">{stat.get("title", "")}</div>
                <div class="stat-value text-{stat.get("color", "primary")}">{stat.get("value", "")}</div>
                <div class="stat-desc">{stat.get("desc", "")}</div>
            </div>
            """
            )

        return Markup(
            f"""
        <div class="stats shadow {orientation} {classes}">
            {''.join(stats_html)}
        </div>
        """
        )
