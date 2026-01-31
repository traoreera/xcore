from typing import Dict, List

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Footer(Component):
    """A responsive footer component with sections, social media links, and a copyright notice."""

    def render(self):
        return self.__render(
            sections=self.props.get("sections", []),
            social_links=self.props.get("social_links", {}),
            copyright_text=self.props.get(
                "copyright_text",
                f"© {self.props.get('year', 2025)} My Company, Inc. All rights reserved.",
            ),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        sections: List[Dict],
        social_links: Dict[str, str],
        copyright_text: str,
        classes: str = "",
    ) -> Markup:

        section_html = ""
        for section in sections:
            links_html = ""
            for link in section.get("links", []):
                links_html += f'<li><a href="{link.get("href", "#")}" class="link link-hover">{link.get("text", "")}</a></li>'

            section_html += f"""
                <div class="footer-col">
                    <h6 class="footer-title">{section.get("title", "")}</h6>
                    <ul class="space-y-2">
                        {links_html}
                    </ul>
                </div>
            """

        social_links_html = ""
        for name, link in social_links.items():
            social_links_html += f'<a href="{link}" class="link link-hover">{name.capitalize()}</a>'

        return Markup(
            f"""
            <footer class="footer p-10 bg-base-200 text-base-content {classes}">
                <div class="container mx-auto grid grid-cols-1 md:grid-cols-4 gap-8">
                    {section_html}
                </div>
                <div class="container mx-auto mt-8 border-t border-base-300 pt-8 flex flex-col md:flex-row justify-between items-center">
                    <p>{copyright_text}</p>
                    <div class="flex gap-4 mt-4 md:mt-0">
                        {social_links_html}
                    </div>
                </div>
            </footer>
        """
        )
