from flask import Flask

app = Flask(__name__)
from run_compare_app import compare  # from my_app import views
