from typing import Dict, List

from markupsafe import Markup

from frontend.microui.core.extension import Component
from frontend.microui.core.register import register


@register
class Breadcrumb(Component):
    """Composant Breadcrumb pour navigation"""

    def render(self):
        
        
        return self.__render(
            items=self.props.get("items", []), 
            classes=self.props.get("class", ""),
            request= self.props.get("request", "")
            )
    

    @staticmethod
    def __render(items: List[Dict], classes: str = "", request=None) -> Markup:
        breadcrumb_items = []
        if items and len(items) > 0:
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                if is_last:
                    breadcrumb_items.append(f'<li>{item.get("text", "")}</li>')
                else:
                    breadcrumb_items.append(
                        f'<li><a href="{item.get("href", "#")}">{item.get("text", "")}</a></li>'
                    )

            return Markup(
                f"""
            <div class="text-sm breadcrumbs {classes}">
                <ul>
                    {''.join(breadcrumb_items)}
                </ul>
            </div>
            """
            )
        
        if request:
            #extract url items from request
            url_items = request.url.path.split("/")
            breadcrumb_items = []
            for i, item in enumerate(url_items):
                is_last = i == len(url_items) - 1
                if is_last:
                    breadcrumb_items.append(f'<li>{item}</li>')
                else:
                    breadcrumb_items.append(
                        f'<li><a href="/{"/".join(url_items[:i+1])}">{item}</a></li>'
                    )

            return Markup(
                f"""
            <div class="text-sm breadcrumbs {classes}">
                <ul>
                    {''.join(breadcrumb_items)}
                </ul>
            </div>
            """
            )
