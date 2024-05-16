from run_compare_app import app

app.secret_key = '1234'
app.config['SESSION_TYPE'] = 'filesystem'

app.run(debug=True)