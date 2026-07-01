from apeiron.library.modules import PROXY_REGISTRY
from apeiron.library.re import Library
from plotly.graph_objects import Figure


def test_plotly_proxy_registered():
    assert "plotly" in PROXY_REGISTRY


def test_plotly_proxy_exposes_chart_endpoints():
    library = Library(bind_libraries=["plotly"])
    proxy = library.proxies["plotly"]

    assert "charts/line" in proxy.registry
    assert "charts/bar" in proxy.registry
    assert "charts/scatter" in proxy.registry
    assert "charts/pie" in proxy.registry
    assert "charts/histogram" in proxy.registry


def test_plotly_bar_endpoint_returns_figure():
    library = Library(bind_libraries=["plotly"])

    fig = library(
        "plotly/charts/bar",
        {
            "records": [
                {"category": "A", "value": 10},
                {"category": "B", "value": 20},
            ],
            "x": "category",
            "y": "value",
            "title": "Values by category",
        },
    )

    assert isinstance(fig, Figure)
    assert fig.layout.title.text == "Values by category"
    assert list(fig.data[0].x) == ["A", "B"]
    assert list(fig.data[0].y) == [10, 20]
