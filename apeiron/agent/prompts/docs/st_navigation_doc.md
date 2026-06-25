
#### st.navigation

def navigation(
    pages: Sequence[PageType] | Mapping[SectionHeader, Sequence[PageType]],
    *,
    position: Literal["sidebar", "hidden", "top"] = "sidebar",
    expanded: bool = False,
) -> StreamlitPage:
    """
    Configure the available pages in a multipage app.

    Call ``st.navigation`` in your entrypoint file to define the available
    pages for your app. ``st.navigation`` returns the current page, which can
    be executed using ``.run()`` method.

    When using ``st.navigation``, your entrypoint file (the file passed to
    ``streamlit run``) acts like a router or frame of common elements around
    each of your pages. Streamlit executes the entrypoint file with every app
    rerun. To execute the current page, you must call the ``.run()`` method on
    the ``StreamlitPage`` object returned by ``st.navigation``.

    The set of available pages can be updated with each rerun for dynamic
    navigation. By default, ``st.navigation`` displays the available pages in
    the sidebar if there is more than one page. This behavior can be changed
    using the ``position`` keyword argument.

    As soon as any session of your app executes the ``st.navigation`` command,
    your app will ignore the ``pages/`` directory (across all sessions).

    Parameters
    ----------
    pages : Sequence[page-like], Mapping[str, Sequence[page-like]]
        The available pages for the app.

        To create a navigation menu with no sections or page groupings,
        ``pages`` must be a list of page-like objects. Page-like objects are
        anything that can be passed to ``st.Page`` or a ``StreamlitPage``
        object returned by ``st.Page``.

        To create labeled sections or page groupings within the navigation
        menu, ``pages`` must be a dictionary. Each key is the label of a
        section and each value is the list of page-like objects for
        that section. If you use ``position="top"``, each grouping will be a
        collapsible item in the navigation menu.

        When you use a string or path as a page-like object, they are
        internally passed to ``st.Page`` and converted to ``StreamlitPage``
        objects. In this case, the page will have the default title, icon, and
        path inferred from its path or filename. To customize these attributes
        for your page, initialize your page with ``st.Page``.

    position : "sidebar", "top", or "hidden"
        The position of the navigation menu. If this is ``"sidebar"``
        (default), the navigation widget appears at the top of the sidebar. If
        this is ``"top"``, the navigation appears in the top header of the app.
        If this is ``"hidden"``, the navigation widget is not displayed.

        If there is only one page in ``pages``, the navigation will be hidden
        for any value of ``position``.

    expanded : bool
        Whether the navigation menu should be expanded. If this is ``False``
        (default), the navigation menu will be collapsed and will include a
        button to view more options when there are too many pages to display.
        If this is ``True``, the navigation menu will always be expanded; no
        button to collapse the menu will be displayed.

        If ``st.navigation`` changes from ``expanded=True`` to
        ``expanded=False`` on a rerun, the menu will stay expanded and a
        collapse button will be displayed.

        The parameter is only used when ``position="sidebar"``.

    Returns
    -------
    StreamlitPage
        The current page selected by the user. To run the page, you must use
        the ``.run()`` method on it.

    Examples
    --------
    The following examples show different possible entrypoint files, each named
    ``streamlit_app.py``. An entrypoint file is passed to ``streamlit run``. It
    manages your app's navigation and serves as a router between pages.

    **Example 1: Use a callable or Python file as a page**

    You can declare pages from callables or file paths. If you pass callables
    or paths to ``st.navigation`` as a page-like objects, they are internally
    converted to ``StreamlitPage`` objects using ``st.Page``. In this case, the
    page titles, icons, and paths are inferred from the file or callable names.

    ``page_1.py`` (in the same directory as your entrypoint file):

    >>> import streamlit as st
    >>>
    >>> st.title("Page 1")

    ``streamlit_app.py``:

    >>> import streamlit as st
    >>>
    >>> def page_2():
    ...     st.title("Page 2")
    >>>
    >>> pg = st.navigation(["page_1.py", page_2])
    >>> pg.run()

    .. output::
        https://doc-navigation-example-1.streamlit.app/
        height: 200px

    **Example 2: Group pages into sections and customize them with ``st.Page``**

    You can use a dictionary to create sections within your navigation menu. In
    the following example, each page is similar to Page 1 in Example 1, and all
    pages are in the same directory. However, you can use Python files from
    anywhere in your repository. ``st.Page`` is used to give each page a custom
    title. For more information, see |st.Page|_.

    Directory structure:

    >>> your_repository/
    >>> ├── create_account.py
    >>> ├── learn.py
    >>> ├── manage_account.py
    >>> ├── streamlit_app.py
    >>> └── trial.py

    ``streamlit_app.py``:

    >>> import streamlit as st
    >>>
    >>> pages = {
    ...     "Your account": [
    ...         st.Page("create_account.py", title="Create your account"),
    ...         st.Page("manage_account.py", title="Manage your account"),
    ...     ],
    ...     "Resources": [
    ...         st.Page("learn.py", title="Learn about us"),
    ...         st.Page("trial.py", title="Try it out"),
    ...     ],
    ... }
    >>>
    >>> pg = st.navigation(pages)
    >>> pg.run()

    .. output::
        https://doc-navigation-example-2.streamlit.app/
        height: 300px


    **Example 3: Use top navigation**

    You can use the ``position`` parameter to place the navigation at the top
    of the app. This is useful for apps with a lot of pages because it allows
    you to create collapsible sections for each group of pages. The following
    example uses the same directory structure as Example 2 and shows how to
    create a top navigation menu.

    ``streamlit_app.py``:

    >>> import streamlit as st
    >>>
    >>> pages = {
    ...     "Your account": [
    ...         st.Page("create_account.py", title="Create your account"),
    ...         st.Page("manage_account.py", title="Manage your account"),
    ...     ],
    ...     "Resources": [
    ...         st.Page("learn.py", title="Learn about us"),
    ...         st.Page("trial.py", title="Try it out"),
    ...     ],
    ... }
    >>>
    >>> pg = st.navigation(pages, position="top")
    >>> pg.run()

    .. output::
        https://doc-navigation-top.streamlit.app/
        height: 300px

    **Example 4: Stateful widgets across multiple pages**

    Call widget functions in your entrypoint file when you want a widget to be
    stateful across pages. Assign keys to your common widgets and access their
    values through Session State within your pages.

    ``streamlit_app.py``:

    >>> import streamlit as st
    >>>
    >>> def page1():
    >>>     st.write(st.session_state.foo)
    >>>
    >>> def page2():
    >>>     st.write(st.session_state.bar)
    >>>
    >>> # Widgets shared by all the pages
    >>> st.sidebar.selectbox("Foo", ["A", "B", "C"], key="foo")
    >>> st.sidebar.checkbox("Bar", key="bar")
    >>>
    >>> pg = st.navigation([page1, page2])
    >>> pg.run()

    .. output::
        https://doc-navigation-multipage-widgets.streamlit.app/
        height: 350px

    .. |st.Page| replace:: ``st.Page``
    .. _st.Page: https://docs.streamlit.io/develop/api-reference/navigation/st.page
    """


#### st.Page

def Page(  # noqa: N802
    page: str | Path | Callable[[], None],
    *,
    title: str | None = None,
    icon: str | None = None,
    url_path: str | None = None,
    default: bool = False,
) -> StreamlitPage:
    """Configure a page for ``st.navigation`` in a multipage app.

    Call ``st.Page`` to initialize a ``StreamlitPage`` object, and pass it to
    ``st.navigation`` to declare a page in your app.

    When a user navigates to a page, ``st.navigation`` returns the selected
    ``StreamlitPage`` object. Call ``.run()`` on the returned ``StreamlitPage``
    object to execute the page. You can only run the page returned by
    ``st.navigation``, and you can only run it once per app rerun.

    A page can be defined by a Python file or ``Callable``.

    Parameters
    ----------
    page : str, Path, or callable
        The page source as a ``Callable`` or path to a Python file. If the page
        source is defined by a Python file, the path can be a string or
        ``pathlib.Path`` object. Paths can be absolute or relative to the
        entrypoint file. If the page source is defined by a ``Callable``, the
        ``Callable`` can't accept arguments.

    title : str or None
        The title of the page. If this is ``None`` (default), the page title
        (in the browser tab) and label (in the navigation menu) will be
        inferred from the filename or callable name in ``page``. For more
        information, see `Overview of multipage apps
        <https://docs.streamlit.io/st.page.automatic-page-labels>`_.

    icon : str or None
        An optional emoji or icon to display next to the page title and label.
        If ``icon`` is ``None`` (default), no icon is displayed next to the
        page label in the navigation menu, and a Streamlit icon is displayed
        next to the title (in the browser tab). If ``icon`` is a string, the
        following options are valid:

        - A single-character emoji. For example, you can set ``icon="🚨"``
            or ``icon="🔥"``. Emoji short codes are not supported.

        - An icon from the Material Symbols library (rounded style) in the
            format ``":material/icon_name:"`` where "icon_name" is the name
            of the icon in snake case.

            For example, ``icon=":material/thumb_up:"`` will display the
            Thumb Up icon. Find additional icons in the `Material Symbols \
            <https://fonts.google.com/icons?icon.set=Material+Symbols&icon.style=Rounded>`_
            font library.

    url_path : str or None
        The page's URL pathname, which is the path relative to the app's root
        URL. If this is ``None`` (default), the URL pathname will be inferred
        from the filename or callable name in ``page``. For more information,
        see `Overview of multipage apps
        <https://docs.streamlit.io/st.page.automatic-page-urls>`_.

        The default page will have a pathname of ``""``, indicating the root
        URL of the app. If you set ``default=True``, ``url_path`` is ignored.
        ``url_path`` can't include forward slashes; paths can't include
        subdirectories.

    default : bool
        Whether this page is the default page to be shown when the app is
        loaded. If ``default`` is ``False`` (default), the page will have a
        nonempty URL pathname. However, if no default page is passed to
        ``st.navigation`` and this is the first page, this page will become the
        default page. If ``default`` is ``True``, then the page will have
        an empty pathname and ``url_path`` will be ignored.

    Returns
    -------
    StreamlitPage
        The page object associated to the given script.

    Example
    -------
    >>> import streamlit as st
    >>>
    >>> def page2():
    >>>     st.title("Second page")
    >>>
    >>> pg = st.navigation([
    >>>     st.Page("page1.py", title="First page", icon="🔥"),
    >>>     st.Page(page2, title="Second page", icon=":material/favorite:"),
    >>> ])
    >>> pg.run()
    """