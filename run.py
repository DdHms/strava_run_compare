from run_compare_app import app
from flask import url_for

def generate_url():
    with app.app_context():  # Explicitly set the application context
        my_url = url_for('login', _external=True)
        print(f"Generated URL: {my_url}")
        return my_url

if __name__ == '__main__':
    app.config['SESSION_TYPE'] = 'filesystem'

    app.run(debug=True, port=3474)