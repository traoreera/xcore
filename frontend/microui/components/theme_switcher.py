
from markupsafe import Markup

from frontend.microui.core.extension import Component
from frontend.microui.core.register import register


@register
class ThemeSwitcher(Component):
    """Gestionnaire de thèmes et composants DaisyUI"""

    THEMES = [
        "light",
        "dark",
        "cupcake",
        "bumblebee",
        "emerald",
        "corporate",
        "synthwave",
        "retro",
        "cyberpunk",
        "valentine",
        "halloween",
        "garden",
        "forest",
        "aqua",
        "lofi",
        "pastel",
        "fantasy",
        "wireframe",
        "black",
        "luxury",
        "dracula",
        "cmyk",
        "autumn",
        "business",
        "acid",
        "lemonade",
        "night",
        "coffee",
        "winter",
        "dim",
        "nord",
        "sunset",
    ]

    def render(self):
        print(self.props)
        return self.__render(
            current_theme=self.props.get("current_theme", "light"),
            position=self.props.get("position", "dropdown-end"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        current_theme: str = "light", position: str = "dropdown-end", classes: str = ""
    ) -> Markup:
        """Sélecteur de thème DaisyUI"""
        theme_items = []
        for theme in ThemeSwitcher.THEMES:
            icon = "🌙" if theme == "dark" else "☀️" if theme == "light" else "🎨"
            theme_items.append(
                f"<li>"
                f'<button class="theme-controller" '
                f'hx-post="/theme/set" '
                f'hx-vals=\'{{"theme": "{theme}"}}\' '
                f'hx-swap="outerHTML" '
                f'hx-target="body">'
                f'<span class="flex items-center gap-2">'
                f"{icon} {theme.capitalize()}"
                f"</span>"
                f"</button>"
                f"</li>"
            )

        themes_html = "\n".join(theme_items)

        # Icon selon le thème actuel
        current_icon = (
            "🌙" if current_theme == "dark" else "☀️" if current_theme == "light" else "🎨"
        )

        return Markup(
            f"""
        <div class="dropdown {position}">
            <div tabindex="0" role="button" class="btn btn-ghost gap-2">
                <span class="text-xl">{current_icon}</span>
                <span class="hidden sm:inline">{current_theme.capitalize()}</span>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="w-4 h-4 stroke-current">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
            </div>
            <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow-2xl bg-base-300 rounded-box w-52 max-h-96 overflow-y-auto mt-4">
                {themes_html}
            </ul>
        </div>
        """
        )

    @staticmethod
    def rendering(
        current_theme: str = "light", position: str = "dropdown-end", classes: str = ""
    ) -> Markup:
        """Static method to render ThemeSwitcher without instantiating the class."""
        return ThemeSwitcher.__render(current_theme, position, classes)
