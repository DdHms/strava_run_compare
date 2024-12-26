from flask import Flask

app = Flask(__name__)
app.secret_key = '1234'
from run_compare_app import compare  # from my_app import views
