from typing import Dict, List, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register
from microui.utils import build_menu_items


@register
class Sidebar(Component):
    """Composant Sidebar avec menu responsive et sous-menus"""

    def render(self):
        return self.__render(
            items=self.props.get("items", []),
            brand=self.props.get("brand"),
            brand_logo=self.props.get("brand_logo"),
            footer=self.props.get("footer"),
            compact=self.props.get("compact", False),
            collapsible=self.props.get("collapsible", True),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        items: List[Dict],
        brand: Optional[str] = None,
        brand_logo: Optional[str] = None,
        footer: Optional[str] = None,
        compact: bool = False,
        collapsible: bool = True,
        classes: str = "",
    ) -> Markup:
        brand_html = ""
        if brand or brand_logo:
            logo = f'<img src="{brand_logo}" class="w-8 h-8" alt="Logo" />' if brand_logo else ""
            brand_html = f"""
            <li class="mb-2">
                <a class="flex items-center gap-2 font-bold text-lg {'justify-center' if compact else ''}" title="{brand or ''}">
                    {logo}
                    {'<span class="sidebar-label">' + brand + '</span>' if brand else ''}
                </a>
            </li>
            """

        menu_items = build_menu_items(items, compact)

        footer_html = (
            f'<div class="p-2 lg:p-4 border-t border-base-300 mt-auto"><span class="sidebar-label lg:inline hidden">{footer}</span></div>'
            if footer
            else ""
        )

        collapse_btn = ""
        if collapsible:
            collapse_btn = """
            <button
                onclick="toggleSidebarCollapse()"
                class="hidden lg:flex btn btn-ghost btn-sm absolute top-4 -right-3 z-50 btn-circle bg-base-300"
                id="collapse-btn"
                aria-label="Réduire/Étendre la sidebar"
            >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-4 h-4 stroke-current">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                </svg>
            </button>
            """

        size_class = (
            "w-64 lg:w-64 transition-width duration-300"
            if not compact
            else "w-12 lg:w-12 transition-width duration-300"
        )

        return Markup(
            f"""
        <div class="drawer-side z-40">
            <label for="sidebar-drawer" class="drawer-overlay lg:hidden"></label>
            <aside id="sidebar" class="menu {size_class} min-h-screen bg-base-200 text-base-content flex flex-col relative {classes}" role="navigation">
                {collapse_btn}
                <ul class="p-2 lg:p-4 flex-1">
                    {brand_html}
                    {menu_items}
                </ul>
                {footer_html}
            </aside>
        </div>
        
        <script>
            function toggleSidebarCollapse() {{
                const sidebar = document.getElementById('sidebar');
                if (!sidebar) return;
                sidebar.classList.toggle('lg:w-12');
                sidebar.classList.toggle('lg:w-64');
                const labels = sidebar.querySelectorAll('.sidebar-label');
                labels.forEach(label => label.classList.toggle('lg:hidden'));
                const details = sidebar.querySelectorAll('details');
                details.forEach(detail => {{
                    detail.classList.toggle('pointer-events-none');
                    detail.classList.toggle('opacity-50');
                    detail.setAttribute('aria-expanded', detail.classList.contains('pointer-events-none') ? 'false' : 'true');
                }});
                const submenus = sidebar.querySelectorAll('details ul');
                submenus.forEach(ul => ul.classList.toggle('hidden'));
                const arrow = document.querySelector('#collapse-btn path');
                if (arrow) {{
                    arrow.setAttribute('d', sidebar.classList.contains('lg:w-12') ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7');
                }}
            }}
        </script>
        """
        )

    @staticmethod
    def rendering(
        items: List[Dict],
        brand: Optional[str] = None,
        brand_logo: Optional[str] = None,
        footer: Optional[str] = None,
        compact: bool = False,
        collapsible: bool = True,
        classes: str = "",
    ) -> Markup:
        return Sidebar.__render(
            items=items,
            brand=brand,
            brand_logo=brand_logo,
            footer=footer,
            compact=compact,
            collapsible=collapsible,
            classes=classes,
        )
