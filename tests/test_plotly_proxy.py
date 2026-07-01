from apeiron.library.modules import PROXY_REGISTRY
from apeiron.library.re import Library


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
