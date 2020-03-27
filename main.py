from flask import request, abort, jsonify, json, render_template, redirect, url_for
import flask
from flask_cors import CORS
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import json
import csv
import pandas as pd
from geopy.geocoders import Nominatim

load_dotenv()

app = flask.Flask(__name__)
app.Debug = os.getenv("DEBUG")
CORS(app)

STATE_DATA = None
geolocator = Nominatim(user_agent="main")

@app.route('/', methods=['GET'])
def main():
    message = ''
    return render_template('index.html', message=message)

def get_stats_loc(lat,lng):
     location = geolocator.reverse(str(lat)+", "+str(lng))
     raw_state = location.raw['address']['state']
     raw_county = location.raw['address']['county']
     raw_county = raw_county[:raw_county.index(" County")]
     print(lat,',',lng,':',STATE_DATA[raw_state][raw_county])


# if __name__ == '__main__':
#     app.run(debug=os.getenv("DEBUG"))

STATE_DATA_URL = "https://covidtracking.com/api/states/daily"
remove = ['dateChecked','pending','total']
def get_state_data(date, data = None):
    date =int(date.strftime("%Y%m%d"))
    if not data:
        data = requests.get(STATE_DATA_URL).json()
    ret = [x for x in data if (x["date"] == date)]
    for x in ret:
        for y in remove:
            if y == x:
                x.pop(y)
    return ret

CITY_DATA_BASE_URL = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/"
def get_county_data(date, data = None):
    url = CITY_DATA_BASE_URL+date.strftime("%m-%d-%Y.csv")
    data = requests.get(url).content.decode('utf-8')
    write = open('temp.csv','w')
    write.write(data)
    write.close()
    cols = ['Admin2','Province_State','Country_Region','Last_Update','Lat','Long_','Confirmed','Deaths']
    # removed_cols: (['FIPS','Recovered','Active','Combined_Key'])
    f = open('temp.csv','r+')
    data = pd.read_csv(f, usecols = cols,)#parse_dates = ["Last_Update"]
    # data.rename(columns = {'Admin2':'City'}, inplace = True) 
    return data[data['Country_Region'].str.contains('US')].to_dict("index")



def aggregate_city_states(date):
    city = get_county_data(date)
    state = get_state_data(date)
    total_data = {}
    for y in city:
        y = city[y]
        if not str(y['Admin2']).lower() == 'nan':
            if not y['Province_State'] in total_data:
                total_data[y['Province_State']] = {}
            total_data[y['Province_State']][y['Admin2']] = y
    total = {}
    return total_data

STATE_DATA =  aggregate_city_states(datetime(2020,3,26))
#get_stats_loc(,)

