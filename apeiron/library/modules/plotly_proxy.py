from typing import Any

import pandas as pd
from sllm.proxies import BaseProxy, ProxyRegistrator


PLOTLY_USAGE = """
Use this library to create Plotly figures from tabular records in generated
Streamlit apps. Example:

    from apeiron_re import CALL_API
    fig = CALL_API(
        "plotly/charts/bar",
        {
            "records": [{"category": "A", "value": 10}, {"category": "B", "value": 20}],
            "x": "category",
            "y": "value",
            "title": "Values by category",
        },
    )
    st.plotly_chart(fig, use_container_width=True)
"""


@ProxyRegistrator(
    path="plotly",
    name="Plotly Chart Builder",
    description=(
        "Local chart helper for creating interactive Plotly figures from tabular "
        "records. Useful for dashboard-style generated Streamlit applications."
    ),
)
class PlotlyProxy(BaseProxy):
    """
    Plotly chart helper.

    This proxy does not call a network API. It creates Plotly figure objects from
    a list of row dictionaries so generated apps can render the result with
    Streamlit's st.plotly_chart.
    """

    def __init__(self, cutoff_date: str = None, use_cache: bool = True):
        super().__init__(cutoff_date, use_cache)
        self.additional_docs = {"Streamlit usage": PLOTLY_USAGE}

    def __call__(self, ep_key: str, params: dict) -> Any:
        if ep_key not in self._entries:
            raise ValueError(f"Endpoint '{ep_key}' is not registered.")
        self._validate_params(ep_key, params)
        return self._entries[ep_key](params)

    def _validate_params(self, ep_key: str, params: dict):
        expected_params = self.registry[ep_key]["params"]
        for key, param_info in expected_params.items():
            clean_key = key.replace("*", "")
            expected_type = param_info[0]
            if key.endswith("*") and clean_key not in params:
                raise ValueError(f"Required parameter '{clean_key}' is missing.")
            if clean_key in params and not isinstance(params[clean_key], expected_type):
                raise ValueError(
                    f"Parameter '{clean_key}' must be of type {expected_type.__name__}."
                )

    def _to_dataframe(self, records: list[dict]) -> pd.DataFrame:
        if not all(isinstance(record, dict) for record in records):
            raise ValueError("Parameter 'records' must be a list of dictionaries.")
        if not records:
            raise ValueError("Parameter 'records' must contain at least one row.")
        return pd.DataFrame(records)

    def _require_columns(self, df: pd.DataFrame, *columns: str):
        missing = [column for column in columns if column and column not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in records: {missing}")

    @BaseProxy.endpoint(
        category="Charts",
        endpoint="line",
        name="Line Chart",
        description="Create an interactive Plotly line chart from tabular records.",
        params={
            "records*": (list, [{"date": "2026-01-01", "value": 10}]),
            "x*": (str, "date"),
            "y*": (str, "value"),
            "color": (str, "segment"),
            "title": (str, "Trend over time"),
        },
        response="plotly.graph_objects.Figure",
    )
    def line(self, params: dict):
        import plotly.express as px

        df = self._to_dataframe(params["records"])
        self._require_columns(df, params["x"], params["y"], params.get("color"))
        return px.line(
            df,
            x=params["x"],
            y=params["y"],
            color=params.get("color"),
            title=params.get("title"),
        )

    @BaseProxy.endpoint(
        category="Charts",
        endpoint="bar",
        name="Bar Chart",
        description="Create an interactive Plotly bar chart from tabular records.",
        params={
            "records*": (list, [{"category": "A", "value": 10}]),
            "x*": (str, "category"),
            "y*": (str, "value"),
            "color": (str, "segment"),
            "title": (str, "Values by category"),
        },
        response="plotly.graph_objects.Figure",
    )
    def bar(self, params: dict):
        import plotly.express as px

        df = self._to_dataframe(params["records"])
        self._require_columns(df, params["x"], params["y"], params.get("color"))
        return px.bar(
            df,
            x=params["x"],
            y=params["y"],
            color=params.get("color"),
            title=params.get("title"),
        )

    @BaseProxy.endpoint(
        category="Charts",
        endpoint="scatter",
        name="Scatter Plot",
        description="Create an interactive Plotly scatter plot from tabular records.",
        params={
            "records*": (list, [{"x_value": 1, "y_value": 10}]),
            "x*": (str, "x_value"),
            "y*": (str, "y_value"),
            "color": (str, "segment"),
            "title": (str, "Scatter plot"),
        },
        response="plotly.graph_objects.Figure",
    )
    def scatter(self, params: dict):
        import plotly.express as px

        df = self._to_dataframe(params["records"])
        self._require_columns(df, params["x"], params["y"], params.get("color"))
        return px.scatter(
            df,
            x=params["x"],
            y=params["y"],
            color=params.get("color"),
            title=params.get("title"),
        )

    @BaseProxy.endpoint(
        category="Charts",
        endpoint="pie",
        name="Pie Chart",
        description="Create an interactive Plotly pie chart from tabular records.",
        params={
            "records*": (list, [{"category": "A", "value": 10}]),
            "names*": (str, "category"),
            "values*": (str, "value"),
            "title": (str, "Share by category"),
        },
        response="plotly.graph_objects.Figure",
    )
    def pie(self, params: dict):
        import plotly.express as px

        df = self._to_dataframe(params["records"])
        self._require_columns(df, params["names"], params["values"])
        return px.pie(
            df,
            names=params["names"],
            values=params["values"],
            title=params.get("title"),
        )

    @BaseProxy.endpoint(
        category="Charts",
        endpoint="histogram",
        name="Histogram",
        description="Create an interactive Plotly histogram from tabular records.",
        params={
            "records*": (list, [{"value": 10}, {"value": 20}]),
            "x*": (str, "value"),
            "color": (str, "segment"),
            "title": (str, "Distribution"),
            "nbins": (int, 20),
        },
        response="plotly.graph_objects.Figure",
    )
    def histogram(self, params: dict):
        import plotly.express as px

        df = self._to_dataframe(params["records"])
        self._require_columns(df, params["x"], params.get("color"))
        return px.histogram(
            df,
            x=params["x"],
            color=params.get("color"),
            title=params.get("title"),
            nbins=params.get("nbins"),
        )
