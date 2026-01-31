from typing import Dict, List, Optional

from markupsafe import Markup

from microui.components import Avatar, Footer, Navbar, ThemeSwitcher
from microui.core.extension import Component
from microui.core.register import register


@register
class BlogLayout(Component):
    """A layout for a blog or a news website."""

    def render(self):
        return self.__render(
            title=self.props.get("title", "My Blog"),
            main_content=self.props.get("main_content", self.children or ""),
            user_name=self.props.get("user_name", "Anonymous"),
            avatar_src=self.props.get("avatar_src"),
            brand_text=self.props.get("brand_text", "My Blog"),
            nav_items=self.props.get("nav_items", []),
            theme=self.props.get("theme", "light"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        title: str,
        main_content: str,
        user_name: str = "Anonymous",
        avatar_src: Optional[str] = None,
        brand_text: str = "My Blog",
        nav_items: List[Dict] = [],
        theme: str = "light",
        classes: str = "",
    ) -> Markup:

        navbar_content = Navbar.render(
            brand=brand_text,
            items=nav_items,
            end_items=f"""
                <div class="flex items-center gap-4">
                    {ThemeSwitcher.render(current_theme=theme)}
                    {Avatar.render(src=avatar_src, placeholder=user_name[0] if user_name else 'A', size="xs", shape="circle")}
                </div>
            """,
        )

        footer_content = Footer.render(
            sections=[
                {
                    "title": "Categories",
                    "links": [
                        {"text": "Technology", "href": "/category/tech"},
                        {"text": "Lifestyle", "href": "/category/lifestyle"},
                        {"text": "Business", "href": "/category/business"},
                    ],
                },
                {
                    "title": "About",
                    "links": [
                        {"text": "About us", "href": "/about"},
                        {"text": "Contact", "href": "/contact"},
                    ],
                },
            ],
            social_links={
                "twitter": "https://twitter.com/user",
                "youtube": "https://youtube.com/user",
                "facebook": "https://facebook.com/user",
            },
            copyright_text="© 2025 My Blog. All rights reserved.",
        )

        return Markup(
            f"""
        <!DOCTYPE html>
        <html lang="en" data-theme="{theme}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title} | {brand_text}</title>
            <link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet" type="text/css" />
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://unpkg.com/htmx.org@1.9.10" defer></script>
            <style>
                .prose {{
                    max-width: 80ch;
                    margin-left: auto;
                    margin-right: auto;
                }}
            </style>
        </head>
        <body class="{classes}">
            {navbar_content}
            <main class="p-4 sm:p-6 lg:p-8">
                <article class="prose lg:prose-xl">
                    {main_content}
                </article>
            </main>
            {footer_content}
        </body>
        </html>
        """
        )
