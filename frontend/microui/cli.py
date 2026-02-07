import importlib
import os

import click

from frontend.microui.core.register import ComponentRegistry


def load_components():
    """Dynamically loads all components from the components directory."""
    components_dir = os.path.join(os.path.dirname(__file__), "components")
    for filename in os.listdir(components_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"microui.components.{filename[:-3]}"
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                click.echo(f"Error importing {module_name}: {e}", err=True)


@click.group()
def cli():
    """A CLI for MicroUI."""
    load_components()


@cli.command()
def list_components():
    """Lists all available MicroUI components."""

    click.echo("Available components:")
    for component_name in sorted(ComponentRegistry._components.keys()):
        click.echo(f"- {component_name}")


@cli.command()
@click.argument("name")
@click.argument("path")
def new_component(name, path):
    """Creates a new MicroUI component."""
    component_name = name.lower()
    class_name = name.capitalize()
    component_path = os.path.join(path, f"{component_name}.py")

    if os.path.exists(component_path):
        click.echo(f"Component '{component_name}' already exists.", err=True)
        return

    if not name:
        click.echo("Component name cannot be empty.", err=True)
        return

    template = f"""from markupsafe import Markup

from frontend.microui.core.extension import Component
from frontend.microui.core.register import register


@register
class {class_name}(Component):
    \"\"\"Component {class_name}\"\"\"

    def render(self):
        return self.__render(
            text=self.props.get("text", self.children or ""),
        )

    @staticmethod
    def __render(text: str) -> Markup:
        return Markup(f"<div>{{text}}</div>")
"""

    with open(component_path, "w") as f:
        f.write(template)

    click.echo(f"Component '{component_name}' created successfully.")


if __name__ == "__main__":
    cli()
