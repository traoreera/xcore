from typing import List, Literal

from markupsafe import Markup

from frontend.microui.core.extension import Component
from frontend.microui.core.register import register


@register
class Table(Component):
    """Composant Table DaisyUI"""

    def render(self):
        return self.__render(
            headers=self.props.get("headers", []),
            rows=self.props.get("rows", []),
            zebra=self.props.get("zebra", False),
            compact=self.props.get("compact", False),
            hoverable=self.props.get("hoverable", True),
            classes=self.props.get("class", ""),
            width=self.props.get("width", "w-full"),
            height=self.props.get("height", "h-auto"),
        )

    @staticmethod
    def __render(
        headers: List[str],
        rows: List[List[str]],
        zebra: bool = False,
        compact: bool = False,
        hoverable: bool = True,
        width: Literal[
            "w-1/4", "w-1/3", "w-1/2", "w-2/3", "w-3/4", "w-full", "w-auto"
        ] = "w-full",
        height: Literal[
            "h-32", "h-48", "h-64", "h-80", "h-96", "h-full", "h-auto"
        ] = "h-auto",
        classes: str = "",
    ) -> Markup:
        css_classes = ["table"]
        if zebra:
            css_classes.append("table-zebra")
        if compact:
            css_classes.append("table-xs")

        headers_html = "".join([f"<th>{h}</th>" for h in headers])

        rows_html = ""
        for row in rows:
            row_class = "hover" if hoverable else ""
            cells_html = "".join([f"<td>{cell}</td>" for cell in row])
            rows_html += f"<tr class='{row_class}'>{cells_html}</tr>"

        return Markup(
            f"""
        <div class="overflow-x-auto {width} {height}">
            <table class="{' '.join(css_classes)} {classes}">
                <thead>
                    <tr>{headers_html}</tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """
        )
