#!/usr/bin/env python

import multiprocessing
import os
import cfscrape
cfscrape.DEFAULT_CIPHERS += ':SHA1'
#import requests
import yaml
import zipfile
from datetime import date
from lxml import html
import sys
#from requests.adapters import HTTPAdapter
#from requests.packages.urllib3.util.retry import Retry


CURSE_URL = 'https://www.curseforge.com/wow/addons/'
CURSE_DOWNLOAD_URL = 'https://media.forgecdn.net/files/'
#CURSE_DOWNLOAD_URL = 'https://addons-origin.cursecdn.com/files/'
CURSEFORGE_PROJECT_URL = 'https://wow.curseforge.com/projects/'
WOWACE_PROJECT_URL = 'https://www.wowace.com/projects'
CONFIG_FILE = 'config.yaml'

# Open local yaml config
with open(CONFIG_FILE) as addon_file:
    data = yaml.load(addon_file, Loader=yaml.FullLoader)
    #data = yaml.load(addon_file, Loader=yaml.FullLoader)
ADDONS_DIR = data['addons_dir'] + '/'

# Colors!
class add_color:
    PURPLE = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END_COLOR = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def check_for_update(addon):
    """Parse the html of the Curse website for the timestamp and special location reference number of the latest
    file available for download"""
    s = cfscrape.create_scraper(delay=10)
    #s = requests.Session()
    #retries = Retry(total=7,
    #                backoff_factor=0.1,
    #                status_forcelist=[ 404, 500, 502, 503, 504, 524, 525 ])
    #s.mount('https://', HTTPAdapter(max_retries=retries))
#
    webpage = s.get(CURSE_URL + data['addons'][addon]['url'] + '/download')

    webpage_text = html.fromstring(webpage.content)
    try:
        LOCATION = webpage_text.xpath('//p[@class="text-sm"]/a/@href')[0].split('/')[-2]
    except IndexError:
        print(add_color.RED, 
              'Error fetching webpage data for {}.'.format(data['addons'][addon]['url']),
              add_color.END_COLOR)
        return (None, None)
    epoch = webpage_text.xpath('//*/abbr[@class="tip standard-date standard-datetime"]/@data-epoch')[0]
    epoch = float(epoch)
    date_modified = str(date.fromtimestamp(epoch))
    
    FILE_UPDATE = ''.join(e for e in date_modified if e.isalnum())

    #month_dict = { "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06", 
    #               "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12" }
    #date_modified = webpage_text.xpath('//span[@class="mr-2 text-gray-500"]/text()')[0].replace(',','').split(' ')
    #FILE_UPDATE = date_modified[4] + month_dict[date_modified[2]] + date_modified[3] 

    return (FILE_UPDATE, LOCATION)

def get_local_file_mtime(addon):
    """Get mtime info for local file"""
    local_file = os.path.getmtime(ADDONS_DIR + data['addons'][addon]['dir'])
    date_modified = str(date.fromtimestamp(local_file))
    LOCAL_FILE_MTIME = ''.join(e for e in date_modified if e.isalnum())
    return LOCAL_FILE_MTIME

def download_addon(addon, location):
    """Multi-step process to figure out the file name. 
    Step 1) Construct our project site url, 
    after vailidating whether the project is wowace or curseforge, 
    which will reveal the addon file name. 
    Step 2) Using the paramaters from the previous HTML parses, we may build our
    actual download url (link to the file), and download the addon.
    Step 3) Addon file will be a .zip, so we unzip the file directly into the ADDONS_DIR
    """
    s = cfscrape.create_scraper() 
    project_webpage = s.get(CURSE_URL + data['addons'][addon]['url'] + '/files/' + location)
    project_webpage_text = html.fromstring(project_webpage.content)
    file = project_webpage_text.xpath('//span[@class="text-sm"]/text()')[0]
    file = file.replace(' ', '%20')

    if len(location) == 6:
        location_1 = location[:3]
        location_2 = location[3:].lstrip("0")
    else:
        location_1 = location[:4]
        location_2 = location[4:].lstrip("0")

    download_url = CURSE_DOWNLOAD_URL + location_1 + '/' + location_2 + '/' + file
    r = s.get(download_url, stream=True)
    with open('/tmp/' + file, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    
    #print(download_url)
    zip_ref = zipfile.ZipFile('/tmp/' + file, 'r')
    zip_ref.extractall(ADDONS_DIR)
    zip_ref.close()
    
    os.utime(ADDONS_DIR + data['addons'][addon]['dir'], None)

def do_stuff(addon):
    """Iterate through the addon list, compare mtimes. 
    If local file is older than the one available for download, download and install.
    """
    FILE_UPDATE, LOCATION = check_for_update(addon)
    if None not in (FILE_UPDATE, LOCATION):
        checked_addon = add_color.PURPLE + data['addons'][addon]['dir'] + add_color.END_COLOR

        if FILE_UPDATE > get_local_file_mtime(addon):
            action = add_color.YELLOW + 'Downloading' + add_color.END_COLOR
            download_addon(addon, LOCATION)
        else:
            action = add_color.GREEN + 'Skipping' + add_color.END_COLOR    
        print('[ {} ]: {}'.format(action, checked_addon))
    else:
        return

def really_do_stuff():
    jobs = []
    for addon in range(0, len(data['addons'])):
        p = multiprocessing.Process(target=do_stuff, args=(addon,))
        jobs.append(p)
        p.start()

if __name__ == '__main__':
    really_do_stuff()
