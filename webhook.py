from flask import Flask, request, json

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        print("Data received from Webhook is: ", request.json)
        return "Webhook received!"


if __name__ == '__main__':
    app.run(debug=True)