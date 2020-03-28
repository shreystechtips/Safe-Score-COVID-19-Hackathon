import requests
from bs4 import BeautifulSoup
import json

url = "https://www.nytimes.com/interactive/2020/us/coronavirus-stay-at-home-order.html"
page = requests.get(url)
soup = BeautifulSoup(page.content, 'html.parser')
script = soup.findAll('script')
values_rm = ['place_nyt_style', 'state', 'city_lat', 'city_lon', 'county_fips', 'population', 'link_order',
             'link_localnews', 'population_fmt']
top_level_rm = ['blurb']

for x in script:
    lookup = 'var NYTG_places = '
    if lookup in x.text:
        x.string.encode('utf-8')
        json_object = json.loads(x.text[x.text.index(
            lookup)+len(lookup):x.text.index('NYTG.watch(')])  # this is the json object

        #open('inhome.json','w').write(x.text[x.text.index(lookup)+len(lookup):x.text.index('NYTG.watch(')])

# clean up json_object
for state_entry in json_object:
    #remove unwanted top level
    for key in top_level_rm:
        state_entry.pop(key, None)
    
    for value in state_entry['values']:

        #remove unwanted values    
        for key in values_rm:
            test = value.pop(key, None)
            print(test)

        #if shelter at home order is statewide, extract value data
        if state_entry['statewide']:    
            for k,v in value.items():
                state_entry.update({k:v})

        #else, sort county and city
        if(value['geography'] == 'city'):
            state_entry['cities'] = []
            temp_dict = {}
            for k,v in value.items():
                temp_dict.update({k:v})
            state_entry['values'].remove(value)
            state_entry['cities'].append(temp_dict)

    #clean value lists (states with statewide orders)
    if state_entry['statewide']:
        del state_entry['values']
    
    #rename remaning values (states without statewide orders) to county data and remove empty lists
    else:
        state_entry['county_data'] = state_entry['values']
        del state_entry['values']
        if(len(state_entry['county_data']) == 0):
            del state_entry['county_data']
        
#print(json_object)

with open('inhome.json', 'w') as output:
    json.dump(json_object , output)
