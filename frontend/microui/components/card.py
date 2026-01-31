from typing import Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Card(Component):
    """Composant Card DaisyUI"""

    def render(self):
        return self.__render(
            title=self.props.get("title"),
            body=self.props.get("body", self.children or ""),
            image=self.props.get("image"),
            actions=self.props.get("actions"),
            compact=self.props.get("compact", False),
            bordered=self.props.get("bordered", False),
            side=self.props.get("side", False),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        title: Optional[str] = None,
        body: str = "",
        image: Optional[str] = None,
        actions: Optional[str] = None,
        compact: bool = False,
        bordered: bool = False,
        side: bool = False,
        classes: str = "",
    ) -> Markup:
        css_classes = ["card", "bg-base-100"]
        
        if isinstance(title,(dict)):
            image = image or title.get("image","")
            title = title.get("name") or title.get("title")
           
        if compact:
            css_classes.append("card-compact")
        if bordered:
            css_classes.append("border")
        if side:
            css_classes.append("card-side")

        image_html = (
            f'<figure><img src="{image}" alt="{title or "Card image"}" /></figure>' if image else ""
        )
        title_html = f"<h2 class='card-title'>{title}</h2>" if title else ""
        actions_html = f"<div class='card-actions justify-end'>{actions}</div>" if actions else ""

        return Markup(
            f"""
        <div class="card {' '.join(css_classes)} {classes}">
            {image_html}
            <div class="card-body">
                {title_html}
                {body}
                {actions_html}
            </div>
        </div>
        """
        )
