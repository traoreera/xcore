from typing import Optional, Literal

from markupsafe import Markup

from frontend.microui.core.extension import Component
from frontend.microui.core.register import register


@register
class Modal(Component):
    """Composant Modal DaisyUI"""

    def render(self):
        return self.__render(
            id=self.props.get("id", "my_modal"),
            title=self.props.get("title", ""),
            content=self.props.get("content", self.children or ""),
            classes=self.props.get("class", ""),
            width=self.props.get("width", "w-1/2"),
            height=self.props.get("height", "h-auto"),
        )

    @staticmethod
    def __render(
        id: str,
        title: str,
        content: str,
        width: Literal['w-1/4', 'w-1/3', 'w-1/2', 'w-2/3', 'w-3/4', 'w-full', 'w-auto'] = 'w-1/2',
        height: Literal['h-32', 'h-48', 'h-64', 'h-80', 'h-96', 'h-full', 'h-auto'] = 'h-auto',
        actions: Optional[str] = None,
        classes: str = ""
    ) -> Markup:
        actions_html = actions or f'<button class="btn" onclick="{id}.close()">Fermer</button>'

        return Markup(
            f"""
        <dialog id="{id}" class="modal {classes}">
            <div class="modal-box {width} {height} max-w-none">
                <h3 class="font-bold text-lg">{title}</h3>
                <div class="py-4">{content}</div>
                <div class="modal-action">
                    <form method="dialog">
                        {actions_html}
                    </form>
                </div>
            </div>
            <form method="dialog" class="modal-backdrop">
                <button>close</button>
            </form>
        </dialog>
        """
        )