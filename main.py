from flask import request, abort, jsonify, json, render_template, redirect, url_for
import flask
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()