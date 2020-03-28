import requests
from bs4 import BeautifulSoup
import json

url = "https://www.nytimes.com/interactive/2020/us/coronavirus-stay-at-home-order.html"
page = requests.get(url)
soup = BeautifulSoup(page.content, 'html.parser')
script = soup.findAll('script')
top_level_keep = ['key']
values_keep = ['formal_order','key','geography',]
top_level_rm = ['blurb']
for x in script:
    lookup = 'var NYTG_places = '
    if lookup in x.text:
        x.string.encode('utf-8')
        thing = json.loads (x.text[x.text.index(lookup)+len(lookup):x.text.index('NYTG.watch(')]) ## this is the json object
        
        open('inhome.json','w').write(x.text[x.text.index(lookup)+len(lookup):x.text.index('NYTG.watch(')])


