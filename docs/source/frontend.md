# frontend - Template Engine & MicroUI Component Library

## Overview

The `frontend` module provides a complete frontend framework with a Jinja2-based template engine and a comprehensive UI component library called MicroUI. It supports DaisyUI theme integration and Micro Frontend (MicroFE) architecture.

## Module Structure

```
frontend/
├── config.py              # Template engine configuration
├── microui/               # MicroUI component library
│   ├── __init__.py        # MicroUI exports
│   ├── cli.py             # CLI commands
│   ├── components/        # UI components (32+ components)
│   │   ├── alert.py
│   │   ├── avatar.py
│   │   ├── badge.py
│   │   ├── breadcrumb.py
│   │   ├── button.py
│   │   ├── card.py
│   │   ├── checkbox.py
│   │   ├── collapse.py
│   │   ├── divider.py
│   │   ├── drawer.py
│   │   ├── dropdown.py
│   │   ├── footer.py
│   │   ├── input.py
│   │   ├── loading.py
│   │   ├── modal.py
│   │   ├── navbar.py
│   │   ├── pagination.py
│   │   ├── progress.py
│   │   ├── radio.py
│   │   ├── select.py
│   │   ├── sidebar.py
│   │   ├── skeleton.py
│   │   ├── stats.py
│   │   ├── swap.py
│   │   ├── table.py
│   │   ├── tabs.py
│   │   ├── textarea.py
│   │   ├── theme_switcher.py
│   │   ├── timeline.py
│   │   ├── toast.py
│   │   └── tooltip.py
│   ├── core/              # Core MicroUI
│   │   ├── config.py      # Configuration
│   │   ├── extension.py   # Extensions
│   │   ├── register.py    # Component registration
│   │   └── theme.py       # DaisyUI theme management
│   ├── layouts/           # Page layouts
│   │   ├── __init__.py
│   │   └── layout.py
│   └── utils/             # Utilities
│       ├── __init__.py
│       └── utils.py
└── engine/                # Template Engine
    ├── __init__.py        # Engine exports
    ├── cache.py           # Template caching
    ├── component.py       # Component system
    ├── engine.py          # Core template engine
    ├── filters.py         # Template filters
    ├── globals.py         # Global template functions
    └── helpers.py         # Template helpers
```

## Template Engine (`engine/`)

### `engine.py`

Core Jinja2-based template engine.

**Class:** `TemplateEngine`

```python
class TemplateEngine:
    """Jinja2 template engine with caching and custom filters"""

    def __init__(self, template_dir: str, cache_enabled: bool = True):
        """Initialize the template engine"""

    def render(self, template_name: str, context: dict = None) -> str:
        """Render a template with context"""

    def register_filter(self, name: str, func: Callable) -> None:
        """Register a custom template filter"""

    def register_global(self, name: str, value: Any) -> None:
        """Register a global template variable"""
```

**Usage:**
```python
from frontend.engine import TemplateEngine

engine = TemplateEngine("templates")
html = engine.render("index.html", {"title": "My Page"})
```

### `component.py`

Component system for template-based components.

```python
class Component:
    """Base class for template components"""

    def __init__(self, name: str, template: str):
        self.name = name
        self.template = template

    def render(self, **kwargs) -> str:
        """Render the component with props"""

class ComponentRegistry:
    """Registry for template components"""

    def register(self, component: Component) -> None:
        """Register a component"""

    def get(self, name: str) -> Optional[Component]:
        """Get a component by name"""

    def render(self, name: str, **props) -> str:
        """Render a registered component"""
```

### `filters.py`

Custom Jinja2 template filters.

**Available Filters:**
```python
# Date formatting
date_format(value, format="%Y-%m-%d")

# Number formatting
number_format(value, decimals=2)

# Text utilities
truncate(value, length=100)
slugify(value)
capitalize_words(value)

# HTML utilities
strip_tags(value)
line_breaks(value)
```

### `globals.py`

Global template functions.

```python
# URL utilities
def url_for(route_name: str, **kwargs) -> str:
    """Generate URL for a route"""

def static_url(path: str) -> str:
    """Generate URL for static file"""

# Component utilities
def component(name: str, **props) -> str:
    """Render a component"""

def include_partial(template: str, **context) -> str:
    """Include a partial template"""
```

### `cache.py`

Template caching system.

```python
class TemplateCache:
    """Cache for compiled templates"""

    def get(self, template_name: str) -> Optional[Template]:
        """Get cached template"""

    def set(self, template_name: str, template: Template) -> None:
        """Cache a compiled template"""

    def invalidate(self, template_name: str = None) -> None:
        """Invalidate cache (all or specific template)"""
```

### `helpers.py`

Template helper functions.

```python
def render_to_string(template_name: str, context: dict = None) -> str:
    """Render template to string"""

def render_to_response(template_name: str, context: dict = None) -> Response:
    """Render template to HTTP response"""
```

## MicroUI Component Library (`microui/`)

### Core (`core/`)

#### `theme.py`

DaisyUI theme management.

```python
class ThemeManager:
    """Manages DaisyUI themes"""

    THEMES = [
        "light", "dark", "cupcake", "bumblebee",
        "emerald", "corporate", "synthwave", "retro",
        "cyberpunk", "valentine", "halloween", "garden",
        "forest", "aqua", "lofi", "pastel", "fantasy",
        "wireframe", "black", "luxury", "dracula",
        "cmyk", "autumn", "business", "acid",
        "lemonade", "night", "coffee", "winter",
        "dim", "nord", "sunset"
    ]

    def get_current_theme(self) -> str:
        """Get current active theme"""

    def set_theme(self, theme: str) -> None:
        """Set active theme"""

    def list_themes(self) -> List[str]:
        """List all available themes"""
```

#### `register.py`

Component registration system.

```python
class ComponentRegister:
    """Central registry for MicroUI components"""

    def register(self, name: str, component_class: type) -> None:
        """Register a component class"""

    def get(self, name: str) -> type:
        """Get component class by name"""

    def create(self, name: str, **props) -> Component:
        """Create component instance"""
```

#### `config.py`

MicroUI configuration.

```python
class MicroUIConfig:
    """Configuration for MicroUI"""

    default_theme: str = "light"
    component_prefix: str = "ui"
    enable_cache: bool = True
    daisyui_version: str = "4.x"
```

### Components (`components/`)

All components follow a consistent API:

```python
class Component:
    """Base component class"""

    def __init__(self, **props):
        self.props = props

    def render(self) -> str:
        """Render component to HTML"""

    def to_dict(self) -> dict:
        """Convert component to dictionary"""
```

#### Alert Component

```python
from microui.components import Alert

alert = Alert(
    type="info",           # info, success, warning, error
    title="Note",
    message="This is an alert",
    dismissible=True
)
html = alert.render()
```

#### Button Component

```python
from microui.components import Button

button = Button(
    label="Click Me",
    variant="primary",     # primary, secondary, accent, info, success, warning, error, ghost, link
    size="md",             # xs, sm, md, lg
    loading=False,
    disabled=False,
    outline=False
)
html = button.render()
```

#### Card Component

```python
from microui.components import Card

card = Card(
    title="Card Title",
    content="Card content here",
    image="/path/to/image.jpg",
    footer="Footer content",
    bordered=True,
    compact=False
)
html = card.render()
```

#### Input Component

```python
from microui.components import Input

input_field = Input(
    name="username",
    type="text",           # text, password, email, number, etc.
    label="Username",
    placeholder="Enter username",
    required=True,
    helper_text="Your login username"
)
html = input_field.render()
```

#### Modal Component

```python
from microui.components import Modal

modal = Modal(
    id="my_modal",
    title="Modal Title",
    content="Modal content",
    actions=[
        {"label": "Cancel", "variant": "ghost"},
        {"label": "Confirm", "variant": "primary"}
    ]
)
html = modal.render()
```

#### Navbar Component

```python
from microui.components import Navbar

navbar = Navbar(
    brand="My App",
    brand_url="/",
    items=[
        {"label": "Home", "url": "/"},
        {"label": "About", "url": "/about"},
        {"label": "Contact", "url": "/contact"}
    ],
    dropdowns=[
        {
            "label": "Services",
            "items": [
                {"label": "Web", "url": "/services/web"},
                {"label": "Mobile", "url": "/services/mobile"}
            ]
        }
    ]
)
html = navbar.render()
```

#### Table Component

```python
from microui.components import Table

table = Table(
    headers=["Name", "Email", "Role"],
    rows=[
        ["John", "john@example.com", "Admin"],
        ["Jane", "jane@example.com", "User"]
    ],
    striped=True,
    hover=True,
    compact=False
)
html = table.render()
```

#### Theme Switcher Component

```python
from microui.components import ThemeSwitcher

switcher = ThemeSwitcher(
    themes=["light", "dark", "cupcake"],
    current="light"
)
html = switcher.render()
```

### Layouts (`layouts/`)

#### `layout.py`

Page layout components.

```python
class Layout:
    """Base layout class"""

    def __init__(self, content: str, **options):
        self.content = content
        self.options = options

    def render(self) -> str:
        """Render the layout"""

class DashboardLayout(Layout):
    """Dashboard layout with sidebar"""

    def __init__(self, content: str, sidebar_items: list, **options):
        super().__init__(content, **options)
        self.sidebar_items = sidebar_items

class AuthLayout(Layout):
    """Authentication page layout"""

    def __init__(self, content: str, **options):
        super().__init__(content, **options)
```

## Usage Examples

### Basic Template Rendering

```python
from frontend.engine import TemplateEngine

engine = TemplateEngine("templates")

# Render with context
html = engine.render("index.html", {
    "title": "Welcome",
    "user": {"name": "John"}
})
```

### Using Components

```python
from microui.components import Button, Card, Alert

# Create components
button = Button(label="Submit", variant="primary")
card = Card(title="My Card", content=button.render())
alert = Alert(type="success", message="Operation completed!")

# Combine and render
html = f"""
{alert.render()}
{card.render()}
"""
```

### FastAPI Integration

```python
from fastapi import FastAPI
from frontend.engine import TemplateEngine

app = FastAPI()
engine = TemplateEngine("templates")

@app.get("/")
async def index():
    html = engine.render("index.html", {"title": "Home"})
    return HTMLResponse(html)
```

### Custom Filter

```python
from frontend.engine import TemplateEngine

engine = TemplateEngine("templates")

@engine.register_filter("uppercase")
def uppercase(value):
    return value.upper()

# Use in template: {{ name | uppercase }}
```

### Theme Configuration

```python
from microui.core.theme import ThemeManager

theme_manager = ThemeManager()

# Set theme
theme_manager.set_theme("dark")

# Get available themes
themes = theme_manager.list_themes()
```

## CLI Commands (`cli.py`)

```bash
# List all components
python -m microui list-components

# Preview a component
python -m microui preview button

# Generate component scaffold
python -m microui generate-component MyComponent

# Build theme CSS
python -m microui build-theme --theme dark
```

## Configuration

Configuration in `config.json`:

```json
{
  "frontend": {
    "template_directory": "templates",
    "static_directory": "static",
    "cache_enabled": true,
    "default_theme": "light",
    "daisyui_themes": ["light", "dark", "cupcake"]
  }
}
```

## Dependencies

- `jinja2` - Template engine
- `markupsafe` - HTML escaping
- `fastapi` - Web framework integration

## Related Documentation

- [xcore.md](xcore.md) - Core application
- [plugins.md](plugins.md) - Plugin development (can extend MicroUI)
