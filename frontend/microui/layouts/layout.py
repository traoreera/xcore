
from markupsafe import Markup

from frontend.microui.core.extension import Component
from frontend.microui.core.register import register


@register
class PageLayout(Component):
    """Composant Layout - Wrapper principal de l'application"""

    def render(self):
        return self._render_layout(
            title=self.props.get("title", "App"),
            theme=self.props.get("theme", "light"),
            mobile_brand=self.props.get("mobile_brand", "App"),
            sidebar=self.props.get("sidebar", ""),
            header_actions=self.props.get("header_actions", ""),
            container_class=self.props.get("container_class", "px-4 py-6 lg:px-8"),
            show_mobile_header=self.props.get("show_mobile_header", True),
            show_theme_toggle=self.props.get("show_theme_toggle", True),
            show_notifications=self.props.get("show_notifications", True),
            custom_head=self.props.get("custom_head", ""),
            children=self.children,
        )

    @staticmethod
    def _render_layout(
        title: str,
        theme: str,
        mobile_brand: str,
        sidebar: str,
        header_actions: str,
        container_class: str,
        show_mobile_header: bool,
        show_theme_toggle: bool,
        show_notifications: bool,
        custom_head: str,
        children: Markup,
    ) -> Markup:
        """Génère le HTML du layout complet"""

        # Head section
        head_html = PageLayout._render_head(title, theme, custom_head)

        # Mobile header
        mobile_header_html = ""
        if show_mobile_header:
            mobile_header_html = PageLayout._render_mobile_header(
                mobile_brand, header_actions, show_theme_toggle, show_notifications
            )

        # Theme toggle script
        theme_script = (
            PageLayout._render_theme_script(theme) if show_theme_toggle else ""
        )

        return Markup(
            f"""
<!DOCTYPE html>
<html lang="fr" data-theme="{theme}">
{head_html}

<body class="min-h-screen bg-base-100 text-base-content antialiased">

<div class="drawer lg:drawer-open">

    <!-- Checkbox pour le toggle du drawer -->
    <input id="sidebar-drawer" type="checkbox" class="drawer-toggle" />

    <!-- CONTENU PRINCIPAL -->
    <div class="drawer-content flex flex-col min-h-screen">
        {mobile_header_html}
        
        <main class="flex-1 {container_class}">
            {children}
        </main>
    </div>

    <!-- SIDEBAR -->
    {sidebar}

</div>

{theme_script}

</body>
</html>
"""
        )

    @staticmethod
    def _render_head(title: str, theme: str, custom_head: str) -> str:
        """Génère la section <head>"""
        return f"""
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="{title}" />
    <title>{title}</title>

    <!-- DaisyUI + Tailwind CSS -->
    <link href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css" rel="stylesheet" />
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- HTMX (optionnel) -->
    <script src="https://unpkg.com/htmx.org@1.9.10" defer></script>
    
    <!-- Custom head content -->
    {custom_head}
</head>
"""

    @staticmethod
    def _render_mobile_header(
        mobile_brand: str,
        header_actions: str,
        show_theme_toggle: bool,
        show_notifications: bool,
    ) -> str:
        """Génère le header mobile"""

        # Theme toggle button
        theme_toggle_html = ""
        if show_theme_toggle:
            theme_toggle_html = """
            <label class="swap swap-rotate btn btn-ghost btn-circle">
                <input type="checkbox" id="theme-toggle" />
                <svg class="swap-on fill-current w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                    <path d="M5.64,17l-.71.71a1,1,0,0,0,0,1.41,1,1,0,0,0,1.41,0l.71-.71A1,1,0,0,0,5.64,17ZM5,12a1,1,0,0,0-1-1H3a1,1,0,0,0,0,2H4A1,1,0,0,0,5,12Zm7-7a1,1,0,0,0,1-1V3a1,1,0,0,0-2,0V4A1,1,0,0,0,12,5ZM5.64,7.05a1,1,0,0,0,.7.29,1,1,0,0,0,.71-.29,1,1,0,0,0,0-1.41l-.71-.71A1,1,0,0,0,4.93,6.34Zm12,.29a1,1,0,0,0,.7-.29l.71-.71a1,1,0,1,0-1.41-1.41L17,5.64a1,1,0,0,0,0,1.41A1,1,0,0,0,17.66,7.34ZM21,11H20a1,1,0,0,0,0,2h1a1,1,0,0,0,0-2Zm-9,8a1,1,0,0,0-1,1v1a1,1,0,0,0,2,0V20A1,1,0,0,0,12,19ZM18.36,17A1,1,0,0,0,17,18.36l.71.71a1,1,0,0,0,1.41,0,1,1,0,0,0,0-1.41ZM12,6.5A5.5,5.5,0,1,0,17.5,12,5.51,5.51,0,0,0,12,6.5Zm0,9A3.5,3.5,0,1,1,15.5,12,3.5,3.5,0,0,1,12,15.5Z"/>
                </svg>
                <svg class="swap-off fill-current w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                    <path d="M21.64,13a1,1,0,0,0-1.05-.14,8.05,8.05,0,0,1-3.37.73A8.15,8.15,0,0,1,9.08,5.49a8.59,8.59,0,0,1,.25-2A1,1,0,0,0,8,2.36,10.14,10.14,0,1,0,22,14.05,1,1,0,0,0,21.64,13Zm-9.5,6.69A8.14,8.14,0,0,1,7.08,5.22v.27A10.15,10.15,0,0,0,17.22,15.63a9.79,9.79,0,0,0,2.1-.22A8.11,8.11,0,0,1,12.14,19.73Z"/>
                </svg>
            </label>
            """

        # Notifications button
        notifications_html = ""
        if show_notifications:
            notifications_html = """
            <div class="dropdown dropdown-end">
                <label tabindex="0" class="btn btn-ghost btn-circle">
                    <div class="indicator">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
                        </svg>
                        <span class="badge badge-xs badge-primary indicator-item">3</span>
                    </div>
                </label>
            </div>
            """

        return f"""
        <header class="navbar bg-base-100 border-b border-base-300 lg:hidden sticky top-0 z-30 shadow-sm">
            <div class="flex-none">
                <label for="sidebar-drawer" class="btn btn-ghost btn-square">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
                    </svg>
                </label>
            </div>
            <div class="flex-1">
                <span class="text-lg font-semibold">{mobile_brand}</span>
            </div>
            <div class="flex-none gap-2">
                {theme_toggle_html}
                {header_actions}
                {notifications_html}
            </div>
        </header>
        """

    @staticmethod
    def _render_theme_script(default_theme: str) -> str:
        """Génère le script de gestion du thème"""
        return f"""
<script>
    // Theme toggle
    (function() {{
        const themeToggle = document.getElementById('theme-toggle');
        const html = document.documentElement;
        
        if (themeToggle) {{
            themeToggle.addEventListener('change', function() {{
                const newTheme = this.checked ? 'dark' : 'light';
                html.setAttribute('data-theme', newTheme);
                localStorage.setItem('theme', newTheme);
            }});
            
            // Load saved theme
            const savedTheme = localStorage.getItem('theme') || 'light';
            html.setAttribute('data-theme', savedTheme);
            themeToggle.checked = savedTheme === 'dark';
        }}
    }})();
</script>
"""
