from typing import Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Drawer(Component):
    """Composant Drawer pour sidebar responsive (mobile + desktop)"""

    def render(self):
        return self.__render(
            sidebar_content=self.props.get("sidebar_content", ""),
            main_content=self.props.get("main_content", self.children or ""),
            drawer_id=self.props.get("drawer_id", "sidebar-drawer"),
            classes=self.props.get("class", ""),
            mobile_header=self.props.get("mobile_header"),
        )

    @staticmethod
    def __render(
        sidebar_content: str,
        main_content: str,
        drawer_id: str = "sidebar-drawer",
        classes: str = "",
        mobile_header: Optional[str] = None,
    ) -> Markup:
        hamburger_btn = """
        <div class="lg:hidden p-4 bg-base-200">
            <label for="sidebar-drawer" class="btn btn-square btn-ghost">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="inline-block w-6 h-6 stroke-current">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </label>
        </div>
        """

        mobile_header_html = (
            f"<div class='lg:hidden'>{mobile_header}</div>" if mobile_header else ""
        )

        return Markup(
            f"""
        <div class="drawer lg:drawer-open {classes}">
            <input id="{drawer_id}" type="checkbox" class="drawer-toggle" />
            
            <div class="drawer-content flex flex-col min-h-screen">
                {hamburger_btn}
                {mobile_header_html}
                <main class="flex-1 p-4 lg:p-6">
                    {main_content}
                </main>
            </div>
            
            {sidebar_content}
        </div>
        """
        )
