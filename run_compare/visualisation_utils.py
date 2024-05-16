import json

import numpy as np
import plotly.graph_objs as go
import plotly.io as pio
from plotly.subplots import make_subplots

pio.renderers.default = "browser"


def plot_intervals(intervals_data):
    dates = [data['date'] for data in intervals_data]
    dates = [data['date'] for data in intervals_data]
    dates = [data['date'] for data in intervals_data]
    dates = [data['date'] for data in intervals_data]
    pass


def plot_to_date(dates, values, deltas, add_to_fig=None, color='rgba(0,200,255,', name='', label=None, separate=False):
    if add_to_fig is None:
        add_to_fig = make_subplots(specs=[[{"secondary_y": True}]])

    x = [d.strftime("%y-%m-%d") for d in dates]
    y = np.array(values)
    y_upper = y + np.array(deltas)
    y_lower = y - np.array(deltas)
    ln_col = color + '1)'
    fill_col = color + '0.5)'
    add_to_fig.add_trace(go.Scatter(x=x, y=y_lower.tolist(), line=dict(color='rgba(255,255,255,0)'), showlegend=False),
                         secondary_y=separate)
    add_to_fig.add_trace(
        go.Scatter(x=x, y=y_upper.tolist(), fill='tonexty', fillcolor=fill_col, line=dict(color='rgba(255,255,255,0)'),
                   showlegend=False, ), secondary_y=separate)

    add_to_fig.add_trace(go.Scatter(x=x, y=y.tolist(), line=dict(color=ln_col, width=2.5), showlegend=False, text=label,
                                    mode='text+lines'),
                         secondary_y=separate)
    date2display = [d.strftime("%b %d") for d in dates]
    # fig.update_layout(xaxis=dict(title='', gridcolor='grey', tickmode='array', tickvals=date2display, ))
    add_to_fig.update_yaxes(title_text=name, secondary_y=separate, color=ln_col)
    if separate:
        max = y_upper.max() * 1.1
        min = y_lower.min() * 0.9
        updated_min = min - (max - min)
        add_to_fig.update_yaxes(range=[updated_min, max], secondary_y=True, color=ln_col)
        full = full_figure_for_development(add_to_fig)
        min, max = full.layout.yaxis.range
        updated_max = max + max - min
        add_to_fig.update_yaxes(range=[min, updated_max], secondary_y=False)
    return add_to_fig


def full_figure_for_development(fig, warn=True, as_dict=False):
    """
    Compute default values for all attributes not specified in the input figure and
    returns the output as a "full" figure. This function calls Plotly.js via Kaleido
    to populate unspecified attributes. This function is intended for interactive use
    during development to learn more about how Plotly.js computes default values and is
    not generally necessary or recommended for production use.

    Parameters
    ----------
    fig:
        Figure object or dict representing a figure

    warn: bool
        If False, suppress warnings about not using this in production.

    as_dict: bool
        If True, output is a dict with some keys that go.Figure can't parse.
        If False, output is a go.Figure with unparseable keys skipped.

    Returns
    -------
    plotly.graph_objects.Figure or dict
        The full figure
    """

    # Raise informative error message if Kaleido is not installed
    try:
        from kaleido.scopes.plotly import PlotlyScope

        scope = PlotlyScope()
    except Exception as e:
        scope = None
    if scope is None:
        raise ValueError(
            """
Full figure generation requires the kaleido package,
which can be installed using pip:
    $ pip install -U kaleido
"""
        )

    if warn:
        import warnings

        warnings.warn(
            "full_figure_for_development is not recommended or necessary for "
            "production use in most circumstances. \n"
            "To suppress this warning, set warn=False"
        )

    fig = json.loads(scope.transform(fig, format="json").decode("utf-8"))
    if as_dict:
        return fig
    else:
        import plotly.graph_objects as go

        return go.Figure(fig, skip_invalid=True)
