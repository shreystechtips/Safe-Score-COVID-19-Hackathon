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

# NOTE: GIT DATA BEFORE 03-22-2020 IS BAD. THE FORMAT DOES NOT MATCH OUT CODE
load_dotenv()

app = flask.Flask(__name__)
app.Debug = os.getenv("DEBUG")
CORS(app)

STATE_DATA = None
PREV_DATA = None
POP_DATA = None
MASTER_DATE = None
geolocator = Nominatim(user_agent="main")


@app.route('/', methods=['GET'])
def main():
    message = ''
    return render_template('index.html', message=message)


def set_data(date):
    return aggregate_city_states(MASTER_DATE), aggregate_city_states(MASTER_DATE-timedelta(days=5))


def get_latest_data_date():
    date = datetime.now()
    url = CITY_DATA_BASE_URL + date.strftime("%m-%d-%Y.csv")
    response = requests.head(url)
    if response.status_code == 404:
        return date-timedelta(days=1)
    else:
        return date

# NOTE: to pass in lat/lng pass in lat= and lng= FLOAT params with ? after url
@app.route('/location/stats', methods=['GET'])
def get_stats_loc(lat=0, lng=0, stringify=True, MASTER_DATE=MASTER_DATE):
    if not MASTER_DATE:
        MASTER_DATE = get_latest_data_date()
        set_data(MASTER_DATE)
    elif (datetime.now() - MASTER_DATE) > timedelta(days=1):
        MASTER_DATE = get_latest_data_date()
        set_data(MASTER_DATE)

    if stringify:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
    location = geolocator.reverse(str(lat)+", "+str(lng))
    raw_state = location.raw['address']['state']
    raw_county = location.raw['address']['county']
    # print(lat, ',', lng, ':', STATE_DATA[raw_state]
    #       [raw_county[:raw_county.index(" County")]])
    # print(POP_DATA[raw_state][raw_county])
    covid = STATE_DATA[raw_state][raw_county[:raw_county.index(" County")]]
    covid_old = PREV_DATA[raw_state][raw_county[:raw_county.index(" County")]]
    pop = POP_DATA[raw_state][raw_county]
    ret = {}
    ret['County'] = raw_county
    ret['Population'] = int(pop['Population'])
    ret['PopDensity'] = float(
        pop['Density per square mile of land area - Population'])
    ret['LandArea'] = float(pop['Area in square miles - Land area'])
    ret['State'] = raw_state
    ret['CountyCoords'] = {'lat': covid['Lat'], 'lng': covid['Long_']}
    ret['Infected'] = covid['Confirmed']
    ret['Infected_Rate_Growth'] = covid['Confirmed']/covid_old['Confirmed']
    ret['Deaths'] = covid['Deaths']
    ret['Death_Rate_Growth'] = covid['Deaths']/covid_old['Deaths']
    ret['Growth_Index'] = covid['Confirmed']/covid_old['Confirmed'] * \
        ret['Infected']/ret['Population'] * covid['Deaths']/covid_old['Deaths']
    if not stringify:
        return ret
    return jsonify(ret), 200


STATE_DATA_URL = "https://covidtracking.com/api/states/daily"
remove = ['dateChecked', 'pending', 'total']


def get_state_data(date, data=None):
    date = int(date.strftime("%Y%m%d"))
    if not data:
        data = requests.get(STATE_DATA_URL).json()
    ret = [x for x in data if (x["date"] == date)]
    for x in ret:
        for y in remove:
            if y == x:
                x.pop(y)
    return ret


CITY_DATA_BASE_URL = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/"


def get_county_data(date, data=None):
    url = CITY_DATA_BASE_URL+date.strftime("%m-%d-%Y.csv")
    data = requests.get(url).content.decode('utf-8')[1:]
    if not os.path.isdir('generated_data'):
        os.makedirs('generated_data')
    FILE_NAME = './generated_data/'+date.strftime('%d%m%Y')+'.csv'
    write = open(FILE_NAME, 'w+')
    try:
        write.write(data)
    except:
        pass
    write.close()
    cols = ['Admin2', 'Province_State', 'Country_Region',
            'Last_Update', 'Lat', 'Long_', 'Confirmed', 'Deaths']
    # removed_cols: (['FIPS','Recovered','Active','Combined_Key'])
    f = open(FILE_NAME, 'r+')
    data = pd.read_csv(f, usecols=cols,)  # parse_dates = ["Last_Update"]
    # data.rename(columns = {'Admin2':'City'}, inplace = True)
    return data[data['Country_Region'].str.contains('US')].to_dict("index")


POP_FILE = './RawData/Census Population Density by County.csv'


def get_pop_data():
    cols = ['Geographic area', 'Geographic area.1', 'Population', 'Housing units',
            'Area in square miles - Land area', 'Density per square mile of land area - Population']
    data = pd.read_csv(open(POP_FILE, 'r'), skiprows=1, usecols=cols)
    data = data[data['Geographic area.1'].str.contains(' County')]
    total_data = {}
    for index, col in data.iterrows():
        state = col['Geographic area'].split(' - ')[1]
        county = col['Geographic area.1']
        if not state in total_data:
            total_data[state] = {}
        total_data[state][county] = col.to_dict()
    return total_data


def aggregate_city_states(date):
    city = get_county_data(date)
    # state = get_state_data(date)
    total_data = {}
    for y in city:
        y = city[y]
        if not str(y['Admin2']).lower() == 'nan':
            if not y['Province_State'] in total_data:
                total_data[y['Province_State']] = {}
            total_data[y['Province_State']][y['Admin2']] = y
    total = {}
    return total_data


POP_DATA = get_pop_data()
# open('pop_data.json','w').write(json.dumps(POP_DATA))
MASTER_DATE = get_latest_data_date()
STATE_DATA, PREV_DATA = set_data(MASTER_DATE)

if __name__ == '__main__':
    app.run(debug=os.getenv("DEBUG"))
