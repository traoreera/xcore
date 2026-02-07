from typing import Dict, List, Optional

from markupsafe import Markup

from frontend.microui.core.extension import Component
from frontend.microui.core.register import register


@register
class Sidebar(Component):
    """Composant Sidebar - Navigation latérale responsive"""

    def render(self):
        return self._render_sidebar(
            brand=self.props.get("brand", "App"),
            brand_logo=self.props.get("brand_logo"),
            brand_href=self.props.get("brand_href", "/"),
            items=self.props.get("items", []),
            active_item=self.props.get("active_item"),
            footer=self.props.get("footer"),
            width=self.props.get("width", "72"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def _render_sidebar(
        brand: str,
        brand_logo: Optional[str],
        brand_href: str,
        items: List[Dict],
        active_item: Optional[str],
        footer: Optional[str],
        width: str,
        classes: str,
    ) -> Markup:
        """Génère le HTML de la sidebar"""

        # Brand section
        brand_html = Sidebar._render_brand(brand, brand_logo, brand_href)

        # Navigation items
        menu_html = Sidebar._render_menu(items, active_item)

        # Footer section
        footer_html = Sidebar._render_footer(footer)

        return Markup(
            f"""
<div class="drawer-side z-40">
    <label for="sidebar-drawer" aria-label="close sidebar" class="drawer-overlay"></label>

    <aside class="
        w-{width} min-h-screen
        bg-base-100
        border-r border-base-300
        flex flex-col
        shadow-xl lg:shadow-none
        {classes}
    ">
        {brand_html}

        <nav class="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
            {menu_html}
        </nav>

        {footer_html}
    </aside>
</div>

<script>
    function toggleSubmenu(id) {{
        const submenu = document.getElementById('submenu-' + id);
        const arrow = document.getElementById(id + '-arrow');
        
        if (submenu && arrow) {{
            submenu.classList.toggle('hidden');
            arrow.classList.toggle('rotate-180');
            
            if (!submenu.classList.contains('hidden')) {{
                submenu.classList.add('submenu-enter');
            }}
        }}
    }}
</script>

<style>
    @keyframes slideDown {{
        from {{
            opacity: 0;
            transform: translateY(-10px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    
    .submenu-enter {{
        animation: slideDown 0.3s ease-out;
    }}
</style>
"""
        )

    @staticmethod
    def _render_brand(brand: str, brand_logo: Optional[str], brand_href: str) -> str:
        """Génère le HTML du brand/logo"""
        if brand_logo:
            logo_html = f'<img src="{brand_logo}" alt="{brand}" class="w-9 h-9 rounded-xl object-cover flex-shrink-0" />'
        else:
            # Initiales comme fallback
            initials = "".join([word[0].upper() for word in brand.split()[:2]])
            logo_html = f"""
            <div class="w-9 h-9 rounded-xl bg-primary flex items-center justify-center text-primary-content font-bold">
                {initials}
            </div>
            """

        return f"""
        <a href="{brand_href}" class="flex items-center gap-3 px-4 py-4 hover:bg-base-200 transition-colors rounded-xl mx-2">
            {logo_html}
            <span class="text-lg font-semibold tracking-tight truncate">{brand}</span>
        </a>
        """

    @staticmethod
    def _render_menu(items: List[Dict], active_item: Optional[str]) -> str:
        """Génère le HTML du menu"""
        menu_html = ""

        for item in items:
            item_id = item.get("id", item.get("label", "").lower().replace(" ", "-"))
            has_submenu = bool(item.get("submenu"))

            if has_submenu:
                menu_html += Sidebar._render_menu_item_with_submenu(
                    item, item_id, active_item
                )
            else:
                menu_html += Sidebar._render_menu_item(item, item_id, active_item)

        return menu_html

    @staticmethod
    def _render_menu_item(item: Dict, item_id: str, active_item: Optional[str]) -> str:
        """Génère un item de menu simple"""
        is_active = item_id == active_item
        active_class = "bg-primary text-primary-content" if is_active else ""

        badge_html = ""
        if item.get("badge"):
            badge_html = f'<span class="ml-auto badge badge-sm badge-primary">{item.get("badge")}</span>'

        return f"""
        <a href="{item.get("href", "#")}"
           class="
           flex items-center gap-3 px-4 py-2.5 rounded-xl
           text-sm font-medium
           hover:bg-base-200
           transition-all
           {active_class}
        ">
            <span class="text-lg flex-shrink-0">{item.get("icon", "•")}</span>
            <span class="truncate flex-1">{item.get("label")}</span>
            {badge_html}
        </a>
        """

    @staticmethod
    def _render_menu_item_with_submenu(
        item: Dict, item_id: str, active_item: Optional[str]
    ) -> str:
        """Génère un item de menu avec sous-menu"""
        is_active = item_id == active_item
        active_class = "bg-primary text-primary-content" if is_active else ""

        submenu_items_html = ""
        for subitem in item.get("submenu", []):
            subitem_id = subitem.get(
                "id", subitem.get("label", "").lower().replace(" ", "-")
            )
            is_sub_active = subitem_id == active_item
            sub_active_class = "bg-base-200 font-semibold" if is_sub_active else ""

            badge_html = ""
            if subitem.get("badge"):
                badge_html = f'<span class="ml-auto badge badge-sm">{subitem.get("badge")}</span>'

            submenu_items_html += f"""
            <a href="{subitem.get("href", "#")}"
               class="
               flex items-center gap-3 px-4 py-2 rounded-lg
               text-sm
               hover:bg-base-200
               transition-colors
               {sub_active_class}
            ">
                <span class="text-base">{subitem.get("icon", "→")}</span>
                <span class="truncate">{subitem.get("label")}</span>
                {badge_html}
            </a>
            """

        return f"""
        <div class="relative">
            <button 
                onclick="toggleSubmenu('{item_id}')"
                class="
                w-full flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl
                text-sm font-medium
                hover:bg-base-200
                transition-all
                {active_class}
            ">
                <div class="flex items-center gap-3">
                    <span class="text-lg flex-shrink-0">{item.get("icon", "•")}</span>
                    <span class="truncate">{item.get("label")}</span>
                </div>
                <svg id="{item_id}-arrow" class="w-4 h-4 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                </svg>
            </button>
            
            <div id="submenu-{item_id}" class="hidden pl-8 mt-1 space-y-1">
                {submenu_items_html}
            </div>
        </div>
        """

    @staticmethod
    def _render_footer(footer: Optional[str]) -> str:
        """Génère le HTML du footer"""
        if not footer:
            return ""

        return f"""
        <div class="px-4 py-3 border-t border-base-300">
            <div class="text-sm">
                {footer}
            </div>
        </div>
        """
