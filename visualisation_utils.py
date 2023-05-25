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


def plot_to_date(dates, values, deltas, fig=None, color='rgba(0,200,255,', name='', label=None, separate=False):
    if fig is None:
        fig = make_subplots(specs=[[{"secondary_y": True}]])

    x = [d.strftime("%y-%m-%d") for d in dates]
    y = np.array(values)
    y_upper = y + np.array(deltas)
    y_lower = y - np.array(deltas)
    ln_col = color + '1)'
    fill_col = color + '0.5)'
    fig.add_trace(go.Scatter(x=x, y=y_lower.tolist(), line=dict(color='rgba(255,255,255,0)'), showlegend=False),
                  secondary_y=separate)
    fig.add_trace(
        go.Scatter(x=x, y=y_upper.tolist(), fill='tonexty', fillcolor=fill_col, line=dict(color='rgba(255,255,255,0)'),
                   showlegend=False, ), secondary_y=separate)

    fig.add_trace(go.Scatter(x=x, y=y.tolist(), line=dict(color=ln_col, width=2.5), showlegend=False, text=label,
                             mode='text+lines'),
                  secondary_y=separate)
    date2display = [d.strftime("%b %d") for d in dates]
    # fig.update_layout(xaxis=dict(title='', gridcolor='grey', tickmode='array', tickvals=date2display, ))
    fig.update_yaxes(title_text=name, secondary_y=separate)
    if separate:
        max = y_upper.max() * 1.1
        min = y_lower.min() * 0.9
        updated_min = min - (max - min)
        fig.update_yaxes(range=[updated_min, max], secondary_y=True)
        full = fig.full_figure_for_development()
        min, max = full.layout.yaxis.range
        updated_max = max + max - min
        fig.update_yaxes(range=[min, updated_max], secondary_y=False)
    return fig
