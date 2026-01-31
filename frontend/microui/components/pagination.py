from typing import Literal

from markupsafe import Markup

from microui.core.extension import Component
from microui.core.register import register


@register
class Pagination(Component):
    """Composant Pagination"""

    def render(self):
        return self.__render(
            current_page=self.props.get("current_page", 1),
            total_pages=self.props.get("total_pages", 1),
            base_url=self.props.get("base_url", "#"),
            size=self.props.get("size", "md"),
            classes=self.props.get("class", ""),
        )

    @staticmethod
    def __render(
        current_page: int,
        total_pages: int,
        base_url: str,
        size: Literal["xs", "sm", "md", "lg"] = "md",
        classes: str = "",
    ) -> Markup:
        size_class = f"join-{size}" if size != "md" else ""

        pages_html = []

        prev_disabled = "btn-disabled" if current_page <= 1 else ""
        pages_html.append(
            f"""
        <a href="{base_url}?page={current_page - 1}"
           class="join-item btn {prev_disabled}">«</a>
        """
        )

        start = max(1, current_page - 2)
        end = min(total_pages, current_page + 2)

        for page in range(start, end + 1):
            active = "btn-active" if page == current_page else ""
            pages_html.append(
                f"""
            <a href="{base_url}?page={page}"
               class="join-item btn {active}">{page}</a>
            """
            )

        next_disabled = "btn-disabled" if current_page >= total_pages else ""
        pages_html.append(
            f"""
        <a href="{base_url}?page={current_page + 1}"
           class="join-item btn {next_disabled}">»</a>
        """
        )

        return Markup(
            f"""
        <div class="join {size_class} {classes}">
            {''.join(pages_html)}
        </div>
        """
        )
