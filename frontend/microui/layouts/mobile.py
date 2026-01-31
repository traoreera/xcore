from typing import Dict, List, Optional

from markupsafe import Markup

from microui.components import Avatar, Navbar, ThemeSwitcher
from microui.core.extension import Component
from microui.core.register import register


@register
class MobileLayout(Component):
    """A mobile-first layout with a top bar for context and a bottom navigation bar."""

    def render(self):
        print(self.props)
        return self.__render(
            title=self.props.get("title", ""),
            nav_items=self.props.get("nav_items", []),
            main_content=self.props.get("main_content", self.children or ""),
            user_name=self.props.get("user_name", "Anonymous"),
            avatar_src=self.props.get("avatar_src"),
            brand_text=self.props.get("brand", "Mobile App"),
            theme=self.props.get("current_theme", "dark"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        title: str,
        nav_items: List[Dict],
        main_content: str,
        user_name: str = "Anonymous",
        avatar_src: Optional[str] = None,
        brand_text: str = "Mobile App",
        theme: str = "light",
        classes: str = "",
    ) -> Markup:

        top_bar = Navbar.rendering(
            brand=f'<div class="text-lg font-bold">{brand_text}</div>',
            items=nav_items,
            end_items=f"""
                <div class="flex items-center gap-4">
                    {ThemeSwitcher.rendering(current_theme=theme)}
                    {Avatar.rendering(src=avatar_src, placeholder=user_name[0] if user_name else 'A', size="xs", shape="circle")}
                </div>
            """,
        )

        return Markup(
            f"""
        <!DOCTYPE html>
        <html lang="en" data-theme="{theme}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet" type="text/css" />
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://unpkg.com/htmx.org@1.9.10" defer></script>
            <style>
                body {{
                    display: flex;
                    flex-direction: column;
                    height: 100vh;
                }}
                .main-content {{
                    flex-grow: 1;
                    overflow-y: auto;
                    padding: 1.5rem;
                    padding-bottom: 70px; /* Space for bottom nav */
                }}
            </style>
        </head>
        <body class="{classes}">
            {top_bar}
            <main class="main-content">
                {main_content}
            </main>
        </body>
        </html>
        """
        )
