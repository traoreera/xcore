from typing import Dict, List, Optional

from markupsafe import Markup

from microui.components import Avatar, Drawer, Dropdown, Navbar, Sidebar, ThemeSwitcher
from microui.core.extension import Component
from microui.core.register import register


@register
class DesktopLayout(Component):
    """A desktop-first layout with a persistent sidebar, navbar, and main content area."""

    def render(self):
        return self.__render(
            title=self.props.get("title", "Desktop App"),
            sidebar_items=self.props.get("sidebar_items", []),
            main_content=self.props.get("main_content", self.children or ""),
            user_name=self.props.get("user_name", "Anonymous"),
            avatar_src=self.props.get("avatar_src"),
            notifications_count=self.props.get("notifications_count", 0),
            brand_text=self.props.get("brand_text", "Desktop App"),
            theme=self.props.get("current_theme", "light"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        title: str,
        sidebar_items: List[Dict],
        main_content: str,
        user_name: str = "Anonymous",
        avatar_src: Optional[str] = None,
        notifications_count: int = 0,
        brand_text: str = "Desktop App",
        theme: str = "light",
        classes: str = "",
    ) -> Markup:

        user_menu_dropdown = Dropdown.rendering(
            button_text=f"""
                <div class="flex items-center gap-2">
                    {Avatar.rendering(src=avatar_src, placeholder=user_name[0] if user_name else 'A', size="xs", shape="circle")}
                    <span class="hidden md:inline">{user_name}</span>
                </div>
            """,
            items=[
                {"text": "Profile", "href": "/profile", "icon": "👤"},
                {"text": "Settings", "href": "/settings", "icon": "⚙️"},
                {"divider": True, "text": "user", "position": "vertical", "color": "base-300"},
                {"text": "Logout", "href": "/logout", "icon": "🚪"},
            ],
            position="dropdown-end",
        )

        notification_bell = Markup(
            f"""
            <button class="btn btn-ghost btn-circle">
                <div class="indicator">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                    </svg>
                    {f'<span class="badge badge-xs badge-primary indicator-item">{notifications_count}</span>' if notifications_count > 0 else ''}
                </div>
            </button>
        """
        )

        navbar_content = Navbar.rendering(
            brand=brand_text,
            items=[],
            end_items=f"""
                <div class="flex items-center gap-4">
                    {notification_bell}
                    {ThemeSwitcher.rendering(current_theme=theme)}
                    {user_menu_dropdown}
                </div>
            """,
        )

        sidebar_content = Sidebar.rendering(
            items=sidebar_items,
            brand=brand_text,
            collapsible=False,  # Not collapsible in desktop view
        )

        return Markup(
            f"""
        <!DOCTYPE html>
        <html lang="en" data-theme="{theme}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title} </title>
            <link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet" type="text/css" />
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://unpkg.com/htmx.org@1.9.10" defer></script>
            <style>
                body {{
                    display: flex;
                }}
                .sidebar {{
                    width: 250px;
                    flex-shrink: 0;
                }}
                .main-content {{
                    flex-grow: 1;
                    display: flex;
                    flex-direction: column;
                }}
                .navbar {{
                    flex-shrink: 0;
                }}
                .content-area {{
                    flex-grow: 1;
                    padding: 1.5rem;
                    overflow-y: auto;
                    background-color: hsl(var(--b2));
                }}
            </style>
        </head>
        <body class="{classes}">
            {sidebar_content}
            <div class="main-content">
            
                <main class="content-area">
                    {main_content}
                </main>
            </div>
        </body>
        </html>
        """
        )
