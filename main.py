from flask import request, abort, jsonify, json, render_template, redirect, url_for
import flask
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

app = flask.Flask(__name__)
app.Debug = os.getenv("DEBUG")
CORS(app)

@app.route('/', methods=['GET'])
def main():
    message = ''
    return render_template('index.html', message=message)

if __name__ == '__main__':
    app.run(debug=os.getenv("DEBUG"))