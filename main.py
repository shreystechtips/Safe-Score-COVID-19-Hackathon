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
import numpy as np
import math

import age_census
import nyt_inhome

np.seterr(divide='ignore')

# NOTE: GIT DATA BEFORE 03-22-2020 IS BAD. THE FORMAT DOES NOT MATCH OUT CODE
load_dotenv()

app = flask.Flask(__name__)
app.Debug = os.getenv("DEBUG")
CORS(app)

STATE_DATA = None
PREV_DATA = None
INHOME_ORDERS = None
POP_DATA = None
POP_AGE_DATA = None

MASTER_DATE = None
geolocator = Nominatim(user_agent=__name__)


@app.route('/', methods=['GET'])
def main():
    message = ''
    return render_template('index.html', message=message)


def set_data(date):
    global STATE_DATA
    STATE_DATA = aggregate_city_states(date)
    global PREV_DATA
    PREV_DATA = aggregate_city_states(date-timedelta(days=5))
    global INHOME_ORDERS
    INHOME_ORDERS = nyt_inhome.scrape()


def get_latest_data_date():
    date = datetime.now()
    url = CITY_DATA_BASE_URL + date.strftime("%m-%d-%Y.csv")
    response = requests.head(url)
    if response.status_code == 404:
        return date-timedelta(days=1)
    else:
        return date


def at_home(geopy_obj):
    for order in INHOME_ORDERS:
        go = 'statename' in order
        if go and order['statename'] == geopy_obj.raw['address']['state']:
            state = order['statename']
            if 'statewide' in order and order['statewide']:
                return True
            if 'cities' in order:
                city = next((x for x in order['cities'] if x['place_fmt']
                             == geopy_obj['address']['city']), None)
                if city:
                    return True
            if 'county_data' in order:
                county = next((x for x in order['county_data']
                               if x['place_fmt'] == geopy_obj.raw['address']['county']), None)
                if county:
                    return True
    return False


def get_loc_json(location):
    global MASTER_DATE
    if STATE_DATA == None:
        MASTER_DATE = get_latest_data_date()
        set_data(MASTER_DATE)
    if not MASTER_DATE:
        MASTER_DATE = get_latest_data_date()
        set_data(MASTER_DATE)
    elif (datetime.now() - MASTER_DATE) > timedelta(days=1):
        MASTER_DATE = get_latest_data_date()
        set_data(MASTER_DATE)

    raw_state = location.raw['address']['state']
    raw_county = location.raw['address']['county']
    # print(lat, ',', lng, ':', STATE_DATA[raw_state]
    #       [raw_county[:raw_county.index(" County")]])
    # print(POP_DATA[raw_state][raw_county])s
    # print(STATE_DATA[raw_state])
    # print(raw_county)
    short_county = raw_county
    if "County" in raw_county:
        short_county = raw_county[:raw_county.index(" County")]
    if "City" in short_county:
        short_county = raw_county[:raw_county.index(" City")]
    covid = STATE_DATA[raw_state][next(
        x for x in STATE_DATA[raw_state] if short_county in x)]
    covid_old = PREV_DATA[raw_state][next(
        (x for x in PREV_DATA[raw_state] if short_county in x))]

    pop = POP_DATA[raw_state][next(
        x for x in POP_DATA[raw_state] if short_county in x)]
    ret = {}
    ret['County'] = raw_county
    ret['Population'] = int(pop['Population'])
    ret['Population Density'] = float(
        pop['Density per square mile of land area - Population'])
    ret['Land Area'] = float(pop['Area in square miles - Land area'])
    ret['State'] = raw_state
    ret['County_Coords'] = {'lat': covid['Lat'], 'lng': covid['Long_']}
    ret['Active Cases'] = covid['Confirmed']
    ret['Infected Rate Growth'] = calculate_divide(
        covid['Confirmed'], covid_old['Confirmed'])
    ret['Deaths'] = covid['Deaths']
    ret['Death Rate Growth'] = calculate_divide(
        covid['Deaths'], covid_old['Deaths'])
    ret['Stay Home'] = at_home(location)
    ret['High Risk Population'] = get_age_pop_for_county(
        raw_state, raw_county, POP_AGE_DATA)
    if(ret['High Risk Population'] <= 0):
        ret['High Risk Population'] = get_age_pop_for_county(
            raw_state, short_county, POP_AGE_DATA)
    set_growth_index(ret)
    return ret


@app.route('/reverse/stats', methods=['GET'])
def get_stats_reverse(loc="", MASTER_DATE=MASTER_DATE, stringify=True):
    if stringify:
        loc = request.args.get("loc")
    location = geolocator.geocode(loc)
    ret = get_loc_json(geolocator.reverse(
        str(location.raw['lat'])+', '+str(location.raw['lon'])))
    if not stringify:
        return ret
    return jsonify(ret), 200


# NOTE: to pass in lat/lng pass in lat= and lng= FLOAT params with ? after url
@app.route('/location/stats', methods=['GET'])
def get_stats_loc(lat=0, lng=0, stringify=True, MASTER_DATE=MASTER_DATE):
    if stringify:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
    location = geolocator.reverse(str(lat)+", "+str(lng))
    ret = get_loc_json(location)
    if not stringify:
        return ret
    return jsonify(ret), 200


def normalize_calc_value(value):
    return (1 if value == 0 else value)


def set_growth_index(ret):
    x = normalize_calc_value(ret['Active Cases'])*normalize_calc_value(ret['Population Density'])*ret['Infected Rate Growth'] * \
        ret['Death Rate Growth']*normalize_calc_value(ret['Deaths']) * \
        ret['High Risk Population'] / \
        ret['Population']/int(os.getenv("DIVIDE_X"))
    i_term = 0.5
    k_term = 100
    r_term = 0.1
    try:
        e_calc = math.pow(math.e, r_term*x)
        val_numerator = i_term*k_term*e_calc
        val_denom = k_term - i_term + i_term*e_calc
        ret['Safe Score'] = math.ceil(val_numerator/val_denom)
    except OverflowError as error:
        ret['Safe Score'] = 100
    print(ret['Safe Score'])
    ret['Safe Score'] = 100 - ret['Safe Score']


def calculate_divide(val1, val2):
    val2 = 1 if val2 == 0 else val2
    return val1/val2


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
    data = pd.read_csv(
        open(POP_FILE, 'r', encoding='ISO-8859-1'), skiprows=1, usecols=cols)
    data = data[data['Geographic area.1'].str.contains(' County')]
    total_data = {}
    for index, col in data.iterrows():
        state = col['Geographic area'].split(' - ')[1]
        county = col['Geographic area.1']
        if not state in total_data:
            total_data[state] = {}
        total_data[state][county] = col.to_dict()
    return total_data


def get_age_pop_for_county(state, county, data):
    data = data[data["STNAME"].str.contains(state)]
    # print(data,state,county)
    if "County".lower() in county.lower():
        county = county[:county.lower().index("county")]
    for i, row in data.iterrows():
        if county in row['CTYNAME']:
            # print(row['TOT_POP'], county)
            return row['TOT_POP']
    return -1


def aggregate_city_states(date):
    city = get_county_data(date)
    # state = get_state_data(date)\
    # for thing in pop_age_data:
    #     print(thing)
    # fix = pop_age_data[~(pop_age_data['CTYNAME'].str.contains("County"))]

    total_data = {}
    for y in city:
        y = city[y]
        if not str(y['Admin2']).lower() == 'nan':
            if not y['Province_State'] in total_data:
                total_data[y['Province_State']] = {}
            total_data[y['Province_State']][y['Admin2']] = y
            #total_data[y['Province_State']][y['Admin2']]['High Risk Population'] = get_age_pop_for_county(y['Province_State'],y['Admin2'],pop_age_data)
    total = {}
    return total_data


POP_DATA = get_pop_data()
POP_AGE_DATA = age_census.population_data()
# open('pop_data.json','w').write(json.dumps(POP_DATA))
MASTER_DATE = get_latest_data_date()
set_data(MASTER_DATE)

if __name__ == '__main__':
    app.run(debug=os.getenv("DEBUG"))
