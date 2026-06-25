#### Installation

pip install streamlit-navigation-bar

#### st_navbar method

def st_navbar(
    pages,
    selected=sentinel,
    logo_path=None,
    logo_page="Home",
    urls=None,
    styles=None,
    options=True,
    adjust=True,
    key=None,
):
    """
    Place a navigation bar in your Streamlit app.
    
    If there is no ``st.set_page_config`` command on the app page,
    ``st_navbar`` must be the first Streamlit command used, and must only be
    set once per page. If there is a ``st.set_page_config`` command, then
    ``st_navbar`` must be the second one, right after it.

    Parameters
    ----------
    pages : list of str
        A list with the name of each page that will be displayed in the
        navigation bar.
    selected : str or None, optional
        The preselected page on first render. It can be a name from `pages`,
        the `logo_page` (when there is a logo) or ``None``. Defaults to the
        `logo_page` value, if there is a logo. In case there is not one,
        defaults to the first page of the `pages` list. When set to ``None``,
        it will initialize empty and return ``None`` until the user selects a
        page.
    logo_path : str, optional
        The absolute path to an SVG file for a logo. It will be shown on the
        left side of the navigation bar. Defaults to ``None``, where no logo is
        displayed.
    logo_page : str or None, default="Home"
        The page value that will be returned when the logo is selected, if
        there is one. Defaults to ``"Home"``. For a non-clickable logo, set
        this to ``None``.
    urls : dict of {str : str}, optional
        A dictionary with the page name as the key and an external URL as the
        value, both as strings. The page name must be contained in the `pages`
        list. The URL will open in a new window or tab. The default is
        ``None``.
    styles : dict of {str : dict of {str : str}}, optional
        Apply CSS styles to desired targets, through a dictionary with the HTML
        tag or pseudo-class name as the key and another dictionary to style it
        as the value. In the second dictionary, the key-value pair is the name
        of a CSS property and the value it takes, both in string format. It
        accepts CSS variables to be passed as values. Defaults to ``None``,
        where just the default style is applied.

        The available HTML tags are: ``"nav"``, ``"div"``, ``"ul"``, ``"li"``,
        ``"a"``, ``"img"`` and ``"span"``.

        The available pseudo-classes are: ``"active"`` and ``"hover"``, which
        direct the styling to the ``"span"`` tag. The menu and sidebar buttons
        are only styled by ``"hover"`` (if they are set to ``True`` in
        `options`). Currently, ``"hover"`` only accepts two CSS properties,
        they are: ``"color"`` and ``"background-color"``.

        To understand the Document Object Model from the navbar, the CSS
        variables and the default style, go to the API reference in the Notes
        section.
    options : bool or dict of {str : bool}, default=True
        Customize the navbar with options that can be toggled on or off. It
        accepts a dictionary with the option name as the key and a boolean as
        the value. The available options are: ``"show_menu"``,
        ``"show_sidebar"``, ``"hide_nav"``, ``"fix_shadow"`` and
        ``"use_padding"``. Check the API reference in the Notes section for a
        description of each one.

        It is also possible to toggle all options to the same state. Simply
        pass ``True`` to `options`, which is the parameter default value, or
        ``False``.
    adjust : bool, default=True
        When set to ``True`` (default), it overrides some Streamlit behaviors
        and makes a series of CSS adjustments to display the navbar correctly.

        In most cases, the CSS adjustments do not interfere with the rest of
        the web app, however there could be some situations where this occurs.
        If this happens, or it is desired to disable all of them, pass
        ``False`` to `adjust` and, when necessary, make your own CSS
        adjustments with ``st.html``.

        If set to ``False``, it will also disable all adjustments made by
        `options`, regardless of whether they are on or off.
    key : str or int, optional
        A string or integer to use as a unique key for the component. If this
        is omitted, a key will be generated for the widget based on its
        content. Multiple navbars of the same type may not share the same key.

    Returns
    -------
    page : str or None
        The page selected by the user. If there has been no interaction yet,
        returns the preselected page or ``None``.

    Notes
    -----
    To learn more about how to use the navbar, check the API reference
    available at:

    https://github.com/gabrieltempass/streamlit-navigation-bar/wiki/API-reference
    
    Examples
    --------
    >>> import streamlit as st
    >>> from streamlit_navigation_bar import st_navbar
    >>> page = st_navbar(
    ...     ["Home", "Documentation", "Examples", "Community", "About"]
    ... )
    >>> st.write(page)

    .. output::
       https://st-navbar-1.streamlit.app/
       height: 300px
    """


#### Usage

Place a navigation bar in your Streamlit app.

If there is no [``st.set_page_config``](https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config) command on the app page, ``st_navbar`` must be the first Streamlit command used, and must only be set once per page. If there is a [``st.set_page_config``](https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config) command, then ``st_navbar`` must be the second one, right after it.

#### Parameters

**pages** : `list of str`  
A list with the name of each page that will be displayed in the navigation bar.

**selected** : `str` or `None`, optional  
The preselected page on first render. It can be a name from *pages*, the *logo_page* (when there is a logo) or ``None``. Defaults to the *logo_page* value, if there is a logo. In case there is not one, defaults to the first page of the *pages* list. When set to ``None``, it will initialize empty and return ``None`` until the user selects a page.

**logo_path** : `str`, optional  
The absolute path to an SVG file for a logo. It will be shown on the left side of the navigation bar. Defaults to ``None``, where no logo is displayed.

**logo_page** : `str` or `None`, `default="Home"`  
The page value that will be returned when the logo is selected, if there is one. Defaults to ``"Home"``. For a non-clickable logo, set this to ``None``.

**urls** : `dict of {str : str}`, optional  
A dictionary with the page name as the key and an external URL as the value, both as strings. The page name must be contained in the *pages* list. The URL will open in a new window or tab. The default is ``None``.

**styles** : `dict of {str : dict of {str : str}}`, optional  
Apply CSS styles to desired targets, through a dictionary with the HTML tag or pseudo-class name as the key and another dictionary to style it as the value. In the second dictionary, the key-value pair is the name of a CSS property and the value it takes, both in string format. It accepts [CSS variables](https://github.com/gabrieltempass/streamlit-navigation-bar/wiki/Usage#css-variables) to be passed as values. Defaults to ``None``, where just the [default style](https://github.com/gabrieltempass/streamlit-navigation-bar/wiki/Usage#default-style) is applied.

The available HTML tags are: ``"nav"``, ``"div"``, ``"ul"``, ``"li"``, ``"a"``, ``"img"`` and ``"span"``. To better understand the structure, check the [Document Object Model](https://github.com/gabrieltempass/streamlit-navigation-bar/wiki/Usage#document-object-model) section.

The available pseudo-classes are: ``"active"`` and ``"hover"``, which direct the styling to the ``"span"`` tag. The menu and sidebar buttons are only styled by ``"hover"`` (if they are set to ``True`` in *options*). Currently, ``"hover"`` only accepts two CSS properties, they are: ``"color"`` and ``"background-color"``.

**options** : `bool` or `dict of {str : bool}`, `default=True`  
Customize the navbar with options that can be toggled on or off. It accepts a dictionary with the option name as the key and a boolean as the value. The available options are: ``"show_menu"``, ``"show_sidebar"``, ``"hide_nav"``, ``"fix_shadow"`` and ``"use_padding"``. Check the [Options](https://github.com/gabrieltempass/streamlit-navigation-bar/wiki/Usage#options) section for a description of each one.

It is also possible to toggle all options to the same state. Simply pass ``True`` to *options*, which is the parameter default value, or ``False``.

**adjust** : `bool`, `default=True`  
When set to ``True`` (default), it overrides some Streamlit behaviors and makes a series of CSS adjustments to display the navbar correctly.

In most cases, the CSS adjustments do not interfere with the rest of the web app, however there could be some situations where this occurs. If this happens, or it is desired to disable all of them, pass ``False`` to *adjust* and, when necessary, make your own CSS adjustments with [``st.html``](https://docs.streamlit.io/develop/api-reference/utilities/st.html).

If set to ``False``, it will also disable all adjustments made by *options*, regardless of whether they are on or off.

**key** : `str` or `int`, optional  
A string or integer to use as a unique key for the component. If this is omitted, a key will be generated for the widget based on its content. Multiple navbars of the same type may not share the same key.

#### Returns

**page** : `str` or `None`  
The page selected by the user. If there has been no interaction yet, returns the preselected page or ``None``.

#### Styles

##### Document Object Model

To style the navigation bar, it is important to understand its Document Object Model (DOM). For example, if a navbar is created with ``pages=["Page one", "Page two"]`` and an SVG logo. On the frontend side, the component builds this DOM (simplified for readability):

``` html
<nav>
  <div>
    <ul>
      <li>
        <a>
          <img src="svg_logo" img/>
        </a>
      </li>
      <li>
        <a>
          <span>Page one</span>
        </a>
      </li>
      <li>
        <a>
          <span>Page two</span>
        </a>
      </li>
    </ul>
  </div>
</nav>
```

Notice that the ``"a"`` tag will style both the logo and the page name. However, the ``"img"`` tag is unique to the logo, just as ``"span"`` is to the page names.

##### CSS variables

The component accepts [theme configuration options](https://docs.streamlit.io/library/advanced-features/theming) to be passed as [CSS variables](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties) in the *styles* dictionary, for example:

``` python
styles = {
    "nav": {
        "background-color": "var(--primary-color)"
    }
}
```

The CSS variables that can be used are:

```
--primary-color
--background-color
--secondary-background-color
--text-color
--font
```

##### Default style

The default navbar, which can be seen in the [basic example](https://github.com/gabrieltempass/streamlit-navigation-bar/wiki/Examples#basic), has its HTML tags styled with the following CSS properties:

``` css
/* HTML tags */
* {
  margin: 0;
  padding: 0;
}
nav {
  align-items: center;
  background-color: var(--secondary-background-color);
  display: flex;
  font-family: var(--font);
  height: 2.875rem;
  justify-content: center;
  padding-left: 2rem;
  padding-right: 2rem;
}
div {
  max-width: 43.75rem;
  width: 100%;
}
ul {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
li {
  align-items: center;
  display: flex;
  list-style: none;
}
a {
  text-decoration: none;
}
img {
  display: flex;
  height: 1.875rem;
}
span {
  color: var(--text-color);
  display: block;
  text-align: center;
}
```

As for the [pseudo-classes](https://developer.mozilla.org/en-US/docs/Web/CSS/Pseudo-classes), they have a different internal implementation. But to understand their default style, think of it as this (simplified for readability):

``` css
/* Pseudo-classes */
span:active {
  color: var(--text-color);
  font-weight: bold;
}
span:hover {
  background-color: transparent;
  color: var(--text-color);
}
```

These HTML tags and pseudo-classes styles can be overridden, by simply passing another value to the respective target and CSS property in the *styles* parameter.

##### Maximum width

A fundamental CSS property to adjust is the ``"max-width"`` for the ``"div"`` tag. Because it controls how much space the page names have between them. The default value is ``"43.75rem"``, which works well in most cases. But if the navbar has a large number of pages, or longer names, it might be necessary to increase the maximum width. Conversely, whenever the navbar has few pages or short names, this value may need to be reduced.

#### Options

The available options and their descriptions are:

`"show_menu"`  
Show Streamlit's menu button in the navbar. When toggled off it hides the button.


`"show_sidebar"`  
Show Streamlit's sidebar button in the navbar. However, it is still needed to use ``st.sidebar`` in the app, in order for the sidebar button to properly appear. Just like Streamlit's default behavior. When toggled off it hides the button.


`"hide_nav"`  
Hide the sidebar navigation widget that Streamlit creates for multipage apps. When toggled off it resumes Streamlit's default behavior and shows the widget.


`"fix_shadow"`  
Fix the shadow of the expanded sidebar, showing it no matter the window width. It is useful when the navbar and the sidebar have the same background color, which they do by default, because the shadow makes it possible to differentiate between the two elements. When toggled off it assumes Streamlit's default behavior, where it applies the shadow only when the window width is below a certain threshold.


`"use_padding"`  
Position the body of the app, in the y axis of the window, `6rem` from the top (if the navbar has a default height). This is the default style used by Streamlit. When toggled off it removes this padding and positions the body right below the navbar.



### Multipager

Currently there are two main ways to use the component in a multipage app (MPA). Both of them are explained below, with their pros and cons.

#### Streamlit's structure

The more obvious approach, is to follow [Streamlit's MPA structure](https://docs.streamlit.io/develop/concepts/multipage-apps) and use [`st.switch_page`](https://docs.streamlit.io/develop/api-reference/navigation/st.switch_page) to programmatically switch pages. Here, the `st_navbar()` function must be called in the main Python file, also known as the entrypoint, and in every Python file inside the pages directory. For example, if the app structure looks like this:

```
your_repository/
├── pages/
│   ├── page_1.py
│   └── page_2.py
└── home.py
```

The `home.py` file serves as the entrypoint, to execute the app with `streamlit run home.py`, and also as the home page. An important note about the pages is that they need to set the *selected* parameter to their respective name. Below is the code for each file of this example and the resulting app.

`home.py`:
``` python
import streamlit as st
from streamlit_navigation_bar import st_navbar

st.set_page_config(initial_sidebar_state="collapsed")

page = st_navbar(["Home", "Page 1", "Page 2"])

if page == "Page 1":
    st.switch_page("pages/page_1.py")
if page == "Page 2":
    st.switch_page("pages/page_2.py")

# Home content goes here, for example:
st.write("Foo")
```

`page_1.py`:
``` python
import streamlit as st
from streamlit_navigation_bar import st_navbar

st.set_page_config(initial_sidebar_state="collapsed")

page = st_navbar(["Home", "Page 1", "Page 2"], selected="Page 1")

if page == "Home":
    st.switch_page("home.py")
if page == "Page 2":
    st.switch_page("pages/page_2.py")

# Page 1 content goes here, for example:
st.write("Bar")
```

`page_2.py`:
``` python
import streamlit as st
from streamlit_navigation_bar import st_navbar

st.set_page_config(initial_sidebar_state="collapsed")

page = st_navbar(["Home", "Page 1", "Page 2"], selected="Page 2")

if page == "Home":
    st.switch_page("home.py")
if page == "Page 1":
    st.switch_page("pages/page_1.py")

# Page 2 content goes here, for example:
st.write("Baz")
```

[![MPA Streamlit](https://github.com/gabrieltempass/streamlit-navigation-bar/raw/main/images/mpa_streamlit.gif)](https://st-navbar-mpa-st.streamlit.app)
[**[App]**](https://st-navbar-mpa-st.streamlit.app) 
[**[Source]**](https://github.com/gabrieltempass/streamlit-navigation-bar/blob/main/examples/mpa_streamlit/home.py)

This approach is the more intuitive one, since it uses Streamlit's official solution for MPA and has all of its benefits. However, when a user clicks to switch to another page, the navbar will briefly glitch. Causing a bad visual experience. The limitation is planned to be fixed in the future, but there is no estimated date for it to happen yet.

#### Recommended structure

The recommended structure for the app works in a different way, but it is still pretty intuitive. It uses conditions with functions to display the page contents programmatically. Where each function contains the content of a single page, and comes from a Python file in the `pages` folder. To treat the `pages` directory as a package that can be imported, there is a `__init__.py` file inside it, with import statements to automatically load the functions from the modules. This is demonstraded by converting the Streamlit example to the recommended file structure:

```
your_repository/
├── pages/
│   ├── __init__.py
│   ├── home.py
│   ├── page_1.py
│   └── page_2.py
└── app.py
```

Notice how the `home.py` file is just a page now, and `app.py` is the entrypoint file to execute the app with `streamlit run app.py`. This is optional, but it is a good practice, because it separates the content from the app setup and configs. Under this structure, [`st.set_page_config`](https://docs.streamlit.io/develop/api-reference/configuration/st.set_page_config) and `st_navbar` must be called only in the main file, and the functions can be imported using `import pages as pg`. Below is the code for each file and the resulting app again.

`app.py`:
``` python
import streamlit as st
from streamlit_navigation_bar import st_navbar
import pages as pg

st.set_page_config(initial_sidebar_state="collapsed")

page = st_navbar(["Home", "Page 1", "Page 2"])

if page == "Home":
    pg.home()
elif page == "Page 1":
    pg.page_1()
elif page == "Page 2":
    pg.page_2()
```

`__init__.py`:
``` python
from .home import home
from .page_1 import page_1
from .page_2 import page_2
```

`home.py`:
``` python
import streamlit as st

def home():
    # Home content goes here, for example:
    st.write("Foo")
```

`page_1.py`:
``` python
import streamlit as st

def page_1():
    # Page 1 content goes here, for example:
    st.write("Bar")
```

`page_2.py`:
``` python
import streamlit as st

def page_2():
    # Page 2 content goes here, for example:
    st.write("Baz")
```

The main advantage of this approach is having a seamless visual experience when switching pages. It also has less code and is more compartmentalized, which is easier to maintain. But it does not enjoy the features of Streamlit MPA structure, like unique URLs for every page, or the ability to use [`st.page_link`](https://docs.streamlit.io/develop/api-reference/widgets/st.page_link) to switch to another page within the app. So, analyze whether this solution meets your needs.

#### Hints

When naming a page in the navigation bar, it is recommended to make it short, single word, and leave the full name in the page content, otherwise it will be too long to show in the navigation bar.


