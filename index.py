from dash import dcc
from dash import html
import dash

from dash_create import app
from dash_create import server
from layouts import page1, page2, page3
import callbacks
# import callbacks_my_team_perf

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

@app.callback(dash.dependencies.Output('page-content', 'children'),
              [dash.dependencies.Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/apps/fantasy-predictions':
         return page1
    elif pathname == '/apps/free-agent-screening':
         return page2
    elif pathname == '/apps/team-performance':
         return page3
    else:
        return page1 # This is the "home page"

if __name__ == '__main__':
    app.run_server(debug=True)