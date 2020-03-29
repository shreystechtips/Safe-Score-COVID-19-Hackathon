import requests
import pandas as pd
import os
import numpy as np

URL_CENSUS_DATA = 'https://www2.census.gov/programs-surveys/popest/datasets/2010-2018/counties/asrh/cc-est2018-alldata.csv'
LOCAL_FILENAME = './RawData/AGE_DATA.csv'


def download_file(url=URL_CENSUS_DATA):
    local_filename = LOCAL_FILENAME
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    # f.flush()
    return local_filename


def population_data(file=LOCAL_FILENAME):
    if not os.path.isfile(file):
        download_file()
    columns = ['STNAME', 'CTYNAME', 'YEAR', 'AGEGRP', 'TOT_POP']
    data = pd.read_csv(open(file, 'r'), usecols=columns)
    data = data[data.YEAR == 11]
    data = data[data.AGEGRP >= 14]
    data = data.groupby(['STNAME', 'CTYNAME'])['TOT_POP'].sum().reset_index()
    return data

# population_json()
