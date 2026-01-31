from typing import Literal, Optional

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Avatar(Component):
    """Composant Avatar"""

    def render(self):
        return self.__render(
            src=self.props.get("src", ""),
            alt=self.props.get("alt", "Avatar"),
            size=self.props.get("size", "md"),
            shape=self.props.get("shape", "circle"),
            online=self.props.get("online", False),
            offline=self.props.get("offline", False),
            placeholder=self.props.get("placeholder"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        src: str,
        alt: str = "Avatar",
        size: Literal["xs", "sm", "md", "lg", "xl"] = "md",
        shape: Literal["circle", "square"] = "circle",
        online: bool = False,
        offline: bool = False,
        placeholder: Optional[str] = None,
        classes: str = "",
    ) -> Markup:
        size_map = {"xs": "w-8", "sm": "w-12", "md": "w-16", "lg": "w-24", "xl": "w-32"}
        size_class = size_map.get(size, "w-16")

        shape_class = "rounded-full" if shape == "circle" else "rounded-xl"

        status = ""
        if online:
            status = "online"
        elif offline:
            status = "offline"

        if placeholder:
            return Markup(
                f"""
            <div class="avatar placeholder {status} {classes}">
                <div class="bg-neutral text-neutral-content {shape_class} {size_class}">
                    <span>{placeholder}</span>
                </div>
            </div>
            """
            )

        return Markup(
            f"""
        <div class="avatar {status} {classes}">
            <div class="{shape_class} {size_class}">
                <img src="{src}" alt="{alt}" />
            </div>
        </div>
        """
        )

    @staticmethod
    def rendering(
        src: str,
        alt: str = "Avatar",
        size: Literal["xs", "sm", "md", "lg", "xl"] = "md",
        shape: Literal["circle", "square"] = "circle",
        online: bool = False,
        offline: bool = False,
        placeholder: Optional[str] = None,
        classes: str = "",
    ) -> Markup:
        """Static method to render Avatar without instantiating the class."""
        return Avatar.__render(src, alt, size, shape, online, offline, placeholder, classes)
