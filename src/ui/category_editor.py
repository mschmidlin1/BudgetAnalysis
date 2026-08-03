"""Native Streamlit hierarchical editor for search_strings categories."""

from __future__ import annotations

import copy
from typing import Any, Sequence, Tuple

import streamlit as st

from storage.config_tools import load_config, save_config


Path = Sequence[int]


def validate_search_strings(search_strings: Any) -> Tuple[bool, str]:
    """Recursively validate search_strings structure used by analysis."""
    if not isinstance(search_strings, list):
        return False, "Configuration must be a JSON list"
    return _validate_items(search_strings, "root")


def _validate_items(items: list, location: str) -> Tuple[bool, str]:
    for i, item in enumerate(items):
        if isinstance(item, str):
            continue
        if isinstance(item, dict):
            if len(item) != 1:
                return (
                    False,
                    f"Category at {location}[{i}] must have exactly one name key",
                )
            name, value = next(iter(item.items()))
            if not isinstance(name, str) or not name.strip():
                return (
                    False,
                    f"Category name at {location}[{i}] must be a non-empty string",
                )
            if not isinstance(value, list):
                return False, f"Category '{name}' must have a list of children"
            ok, msg = _validate_items(value, f"{location}/{name.strip()}")
            if not ok:
                return False, msg
            continue
        return (
            False,
            f"Item at {location}[{i}] must be a string keyword or category object",
        )
    return True, ""


def normalize_search_strings(search_strings: list) -> list:
    """Return a deep-copied structure with stripped names/keywords."""

    def normalize_items(items: list) -> list:
        normalized: list = []
        for item in items:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    normalized.append(text)
            elif isinstance(item, dict) and len(item) == 1:
                name, children = next(iter(item.items()))
                if isinstance(name, str) and name.strip() and isinstance(children, list):
                    normalized.append({name.strip(): normalize_items(children)})
        return normalized

    return normalize_items(copy.deepcopy(search_strings))


def get_children_list(root: list, path: Path) -> list:
    """Return the node list at path (empty path = root)."""
    current: Any = root
    for idx in path:
        item = current[idx]
        if not isinstance(item, dict) or len(item) != 1:
            raise IndexError(f"Path index {idx} does not point to a category")
        current = next(iter(item.values()))
        if not isinstance(current, list):
            raise IndexError(f"Category at index {idx} has no children list")
    return current


def add_category(root: list, path: Path, name: str) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Category name cannot be empty")
    get_children_list(root, path).insert(0, {name: []})


def add_keyword(root: list, path: Path, keyword: str) -> None:
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("Keyword cannot be empty")
    get_children_list(root, path).insert(0, keyword)


def delete_item(root: list, path: Path, index: int) -> None:
    children = get_children_list(root, path)
    del children[index]


def rename_category(root: list, path: Path, index: int, new_name: str) -> None:
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("Category name cannot be empty")
    children = get_children_list(root, path)
    item = children[index]
    if not isinstance(item, dict) or len(item) != 1:
        raise ValueError("Selected item is not a category")
    old_children = next(iter(item.values()))
    children[index] = {new_name: old_children}


def update_keyword(root: list, path: Path, index: int, new_text: str) -> None:
    new_text = new_text.strip()
    if not new_text:
        raise ValueError("Keyword cannot be empty")
    children = get_children_list(root, path)
    if not isinstance(children[index], str):
        raise ValueError("Selected item is not a keyword")
    children[index] = new_text


def _path_key(path: Path) -> str:
    return "r" if not path else "_".join(str(i) for i in path)


def ensure_category_draft() -> None:
    """Initialize category draft and UI version keys in session state."""
    if "category_draft" not in st.session_state:
        st.session_state.category_draft = copy.deepcopy(load_config())
    if "category_ui_key" not in st.session_state:
        st.session_state.category_ui_key = 0


def refresh_category_draft_from_storage() -> None:
    """Reload draft from storage and bump widget keys."""
    st.session_state.category_draft = copy.deepcopy(load_config())
    st.session_state.category_ui_key = st.session_state.get("category_ui_key", 0) + 1
    st.session_state.config_key = st.session_state.get("config_key", 0) + 1


def set_category_draft(search_strings: list) -> None:
    """Replace draft after a successful save from either editor."""
    st.session_state.category_draft = copy.deepcopy(search_strings)
    st.session_state.category_ui_key = st.session_state.get("category_ui_key", 0) + 1
    st.session_state.config_key = st.session_state.get("config_key", 0) + 1


def _bump_ui() -> None:
    """Bump widget keys so both editors refresh from the latest draft."""
    st.session_state.category_ui_key = st.session_state.get("category_ui_key", 0) + 1
    st.session_state.config_key = st.session_state.get("config_key", 0) + 1


def _render_nodes(path: Path, ui_key: int) -> None:
    children = get_children_list(st.session_state.category_draft, path)
    pk = _path_key(path)

    categories = [
        (index, item)
        for index, item in enumerate(children)
        if isinstance(item, dict) and len(item) == 1
    ]
    keywords = [
        (index, item)
        for index, item in enumerate(children)
        if isinstance(item, str)
    ]

    if not children:
        st.caption("No categories or keywords here yet.")

    if st.button("➕ Add keyword", key=f"add_kw_btn_{ui_key}_{pk}"):
        add_keyword(st.session_state.category_draft, path, "NEW")
        _bump_ui()
        st.rerun(scope="fragment")

    for index, item in keywords:
        item_key = f"{ui_key}_{pk}_{index}"
        kw_col, del_col = st.columns([5, 1])
        with kw_col:
            edited = st.text_input(
                "Keyword",
                value=item,
                key=f"kw_edit_{item_key}",
                label_visibility="collapsed",
            )
        with del_col:
            if st.button("Delete", key=f"del_kw_{item_key}", use_container_width=True):
                delete_item(st.session_state.category_draft, path, index)
                _bump_ui()
                st.rerun(scope="fragment")

        if edited is not None and edited.strip() and edited.strip() != item:
            update_keyword(
                st.session_state.category_draft, path, index, edited
            )

    if st.button("📁 New", key=f"add_cat_btn_{ui_key}_{pk}"):
        add_category(st.session_state.category_draft, path, "NEW FOLDER")
        _bump_ui()
        st.rerun(scope="fragment")

    for index, item in categories:
        child_path = list(path) + [index]
        item_key = f"{ui_key}_{pk}_{index}"
        name, _sub = next(iter(item.items()))
        with st.expander(f"📁 {name}", expanded=False):
            rename_col, apply_col, delete_col = st.columns([3, 1, 1])
            with rename_col:
                renamed = st.text_input(
                    "Rename category",
                    value=name,
                    key=f"rename_cat_{item_key}",
                    label_visibility="collapsed",
                )
            with apply_col:
                if st.button(
                    "Rename",
                    key=f"rename_btn_{item_key}",
                    use_container_width=True,
                ):
                    try:
                        if (renamed or "").strip() != name:
                            rename_category(
                                st.session_state.category_draft,
                                path,
                                index,
                                renamed or "",
                            )
                            _bump_ui()
                            st.rerun(scope="fragment")
                    except ValueError as exc:
                        st.error(str(exc))
            with delete_col:
                if st.button(
                    "Delete",
                    key=f"del_cat_{item_key}",
                    use_container_width=True,
                ):
                    delete_item(st.session_state.category_draft, path, index)
                    _bump_ui()
                    st.rerun(scope="fragment")

            _render_nodes(child_path, ui_key)


def _inject_sticky_toolbar_css() -> None:
    """Pin only the toolbar's layout wrapper; do not sticky large ancestors."""
    # Streamlit 1.55 wraps keyed containers in stLayoutWrapper. Sticky must be on
    # that wrapper (direct-child :has) so its parent is the tall editor body.
    # Sticking the inner block alone fails (parent is only as tall as the toolbar).
    # Broad ancestor :has() selectors pin whole page sections and cause overlap.
    st.markdown(
        """
<style>
div[data-testid="stLayoutWrapper"]:has(> div.st-key-category_editor_toolbar) {
  position: sticky;
  top: 2.875rem;
  z-index: 100;
  background-color: #ffffff;
  padding-top: 0.25rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid rgba(49, 51, 63, 0.2);
}
@media (prefers-color-scheme: dark) {
  div[data-testid="stLayoutWrapper"]:has(> div.st-key-category_editor_toolbar) {
    background-color: #0e1117;
    border-bottom-color: rgba(250, 250, 250, 0.2);
  }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_save_reset_toolbar() -> None:
    """Render the sticky Save / Reset toolbar (single instance)."""
    with st.container(key="category_editor_toolbar", border=True):
        save_col, reset_col, _ = st.columns([1, 1, 4])
        with save_col:
            if st.button(
                "💾 Save", key="category_editor_save", use_container_width=True
            ):
                draft = st.session_state.category_draft
                ok, msg = validate_search_strings(draft)
                if not ok:
                    st.error(f"❌ {msg}")
                else:
                    normalized = normalize_search_strings(draft)
                    try:
                        if save_config(normalized):
                            set_category_draft(normalized)
                            st.success("✅ Configuration saved successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save configuration")
                    except Exception as exc:
                        st.error(f"❌ Error saving configuration: {exc}")
        with reset_col:
            if st.button(
                "🔄 Reset to Saved",
                key="category_editor_reset",
                use_container_width=True,
            ):
                refresh_category_draft_from_storage()
                st.rerun()


@st.fragment
def render_category_editor() -> None:
    """Render the visual category editor with Save / Reset toolbar.

    Fragment-scoped so keyword/category edits do not rerun the full app.
    Save / Reset still trigger a full ``st.rerun()`` to sync the JSON editor.
    """
    ensure_category_draft()
    ui_key = st.session_state.category_ui_key

    st.caption(
        "Edit nested categories and keywords visually. Changes are kept in this "
        "session until you click Save."
    )

    # Wrap toolbar + tree so the sticky toolbar's parent is tall enough to pin
    # while scrolling expanders, without including Ignore/Analysis below.
    with st.container(key="category_editor_body"):
        _inject_sticky_toolbar_css()
        _render_save_reset_toolbar()
        st.divider()
        _render_nodes([], ui_key)
