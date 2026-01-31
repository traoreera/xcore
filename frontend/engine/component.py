# app/engine/component_extension.py

import re
from pathlib import Path

import jinja2
from jinja2 import nodes
from jinja2.ext import Extension
from markupsafe import Markup


class ComponentRegistry:
    """Registry to store component templates."""

    _components = {}

    @classmethod
    def register(cls, name, template):
        cls._components[name] = template

    @classmethod
    def get(cls, name):
        return cls._components.get(name)


class ComponentExtension(Extension):
    """Extension that handles {% component %} tags with async support."""

    tags = {"component"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        component_name = parser.parse_expression()

        props = []
        while parser.stream.current.type != "block_end":
            key = parser.parse_assign_target()
            parser.stream.expect("assign")
            value = parser.parse_expression()
            props.append(nodes.Keyword(key.name, value))

        body = parser.parse_statements(("name:endcomponent",), drop_needle=True)

        return nodes.CallBlock(
            self.call_method("_render_async", [component_name], props), [], [], body
        ).set_lineno(lineno)

    async def _render_async(self, name, caller, **props):
        """Async version of render that properly awaits caller()."""
        template = ComponentRegistry.get(name)
        if not template:
            return f"<!-- Component '{name}' not found -->"

        try:
            # Await caller only once
            slot_content = await caller()
            slot_markup = Markup(slot_content) if slot_content else Markup("")

            # Check if template is a component object
            if hasattr(template, "render") and callable(template.render):
                template.props = props
                template.props["slot"] = slot_markup
                template.props["children"] = slot_markup
                template.children = slot_markup
                return template.render()

            # Template string approach
            props["slot"] = slot_markup
            props["children"] = slot_markup
            template_obj = self.environment.from_string(template)
            return await template_obj.render_async(**props)

        except Exception as e:
            import traceback

            traceback.print_exc()
            return f"<!-- Error rendering component '{name}': {e} -->"


class ComponentExtensions(Extension):
    """Preprocessor for <component.X> syntax with proper nesting support."""

    def preprocess(self, source, name, filename=None):
        """Convert <component.X> to {% component %} tags."""
        converted = self._convert_components(source)
        return converted

    def _convert_components(self, source: str) -> str:
        """Convert <component.X> syntax to {% component %} with proper nesting."""

        def parse_props(props_str: str) -> str:
            """Parse HTML-like attributes to Jinja2 kwargs."""
            if not props_str.strip():
                return ""

            props = []
            pattern = r'(\w+)=(?:"([^"]*)"|\'([^\']*)\'|(\d+\.?\d*)|(\w+))'
            matches = re.findall(pattern, props_str)

            for match in matches:
                key = match[0]
                if match[1]:  # Double quotes
                    if "{{" in match[1] or "{%" in match[1]:
                        props.append(f"{key}={match[1]}")
                    else:
                        props.append(f'{key}="{match[1]}"')
                elif match[2]:  # Single quotes
                    if "{{" in match[2] or "{%" in match[2]:
                        props.append(f"{key}={match[2]}")
                    else:
                        props.append(f'{key}="{match[2]}"')
                elif match[3]:  # Numbers
                    props.append(f"{key}={match[3]}")
                elif match[4]:  # Boolean or bare words
                    lower = match[4].lower()
                    if lower in ("true", "false", "none", "null"):
                        props.append(f"{key}={lower}")
                    else:
                        props.append(f"{key}={match[4]}")

            return " " + " ".join(props) if props else ""

        def convert_recursive(text: str) -> str:
            """Recursively convert components from innermost to outermost."""

            # Self-closing components first
            self_closing_pattern = re.compile(r"<component\.(\w+)([^/]*)/>")

            def replace_self_closing(match):
                name, props_str = match.groups()
                props = parse_props(props_str)
                return f'{{% component "{name}"{props} %}}{{% endcomponent %}}'

            text = re.sub(self_closing_pattern, replace_self_closing, text)

            # Block components - innermost first
            inner_pattern = re.compile(
                r"<component\.(\w+)([^>]*)>((?:(?!<component\.).)*?)</component\.\1>", re.DOTALL
            )

            previous = None
            while previous != text:
                previous = text

                def replace_block(match):
                    name, props_str, slot_content = match.groups()
                    props = parse_props(props_str)
                    return f'{{% component "{name}"{props} %}}{slot_content}{{% endcomponent %}}'

                text = re.sub(inner_pattern, replace_block, text)

            return text

        return convert_recursive(source)


def auto_register_components(folder):
    """_summary_

    Args:
        folder (str): path to folder containing components
    """
    folder = Path(folder)
    if not folder.exists():
        return

    for file in folder.glob("*.html"):
        ComponentRegistry.register(file.stem, file.read_text())
