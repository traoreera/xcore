from typing import List, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Navbar(Component):
    """Composant Navbar DaisyUI"""

    def render(self):
        return self.__render(
            brand=self.props.get("brand", ""),
            items=self.props.get("items", []),
            end_items=self.children,
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        brand: str, items: List[dict], end_items: Optional[str] = None, classes: str = ""
    ) -> Markup:
        
        # verifier si items est une fonction
        if callable(items):
            items = items()


        nav_items = "".join(
            [
                f'<li><a href="{item.get("href", "#")}" '
                f'{"hx-get=\"" + item["hx_get"] + "\"" if item.get("hx_get") else ""}>'
                f'{item["text"]}</a></li>'
                for item in items
            ]
        )

        end_html = f'<div class="navbar-end">{end_items}</div>' if end_items else ""
        return Markup(
            f"""
        <div class="navbar bg-base-100 shadow-lg sticky top-0 z-50 {classes if classes else ""}">
            <div class="navbar-start">
                <div class="dropdown">
                    <div tabindex="0" role="button" class="btn btn-ghost lg:hidden">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h8m-8 6h16" />
                        </svg>
                    </div>
                    <ul tabindex="0" class="menu menu-sm dropdown-content mt-3 z-[1] p-2 shadow bg-base-100 rounded-box w-52">
                        {nav_items}
                    </ul>
                </div>
                <a href='/' class="btn btn-ghost text-xl">{brand}</a>
            </div>
            <div class="navbar-center hidden lg:flex">
                <ul class="menu menu-horizontal px-1">
                    {nav_items}
                </ul>
            </div>
            {end_html}
        </div>
        """
        )

    @staticmethod
    def rendering(
        brand: str, items: List[dict], end_items: Optional[str] = None, classes: str = ""
    ):
        """Static method to render Navbar without instantiating the class."""
        return Navbar.__render(brand, items, end_items, classes)
