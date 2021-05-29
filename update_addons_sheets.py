#!/usr/bin/env python2

import os
#import yaml
import zipfile
import multiprocessing
import requests
from lxml import html
from datetime import date
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from __future__ import print_function
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

# Setup the Sheets API
SCOPES = 'https://www.googleapis.com/auth/spreadsheets.readonly'
store = file.Storage('credentials.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_secret.json', SCOPES)
    creds = tools.run_flow(flow, store)
service = build('sheets', 'v4', http=creds.authorize(Http()))

# Call the Sheets API
#SPREADSHEET_ID = '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms'
SPREADSHEET_ID = '1JYHBSWJs-7uWqGuqQG3_No1t6PR1y1LNylai3B4ET18'
#RANGE_NAME = 'Class Data!A2:E'
RANGE_NAME = 'Addons!A2:E'
result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID,
                                             range=RANGE_NAME).execute()
values = result.get('values', [])

addons = {}

if not values:
    print('No data found.')
else:
    for row in values:
        addons[row[0]] = row[1] 

RANGE_NAME = 'addonsDir!A1'
result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID,
                                             range=RANGE_NAME).execute()
values = result.get('values', [])
ADDONS_DIR = row[0]
print(ADDONS_DIR)


CURSE_URL = "https://www.curseforge.com/wow/addons/"
CURSE_DOWNLOAD_URL = "https://addons-origin.cursecdn.com/files/"
CURSEFORGE_PROJECT_URL = "https://wow.curseforge.com/projects/"
WOWACE_PROJECT_URL = "https://www.wowace.com/projects"
CURSE_ADDON_FILE = "curse.yaml"

# Open local yaml config
#with open(CURSE_ADDON_FILE) as addon_file:
#    addons = yaml.load(addon_file)
#ADDONS_DIR = addons["addonsDir"]

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

    s = requests.Session()
    retries = Retry(total=7,
                    backoff_factor=0.1,
                    status_forcelist=[ 404, 500, 502, 503, 504 ])
    s.mount('https://', HTTPAdapter(max_retries=retries))

    webpage = s.get(CURSE_URL + addon + '/download')
    webpage_text = html.fromstring(webpage.content)
  
    LOCATION = webpage_text.xpath('//p[@class=""]/a/@href')[0].split('/')[-2]
    epoch = webpage_text.xpath('//span[@class="stats--last-updated"]/abbr[@class="tip standard-date standard-datetime"]/@data-epoch')[0]
    epoch = float(epoch)
    date_modified = str(date.fromtimestamp(epoch))
    FILE_UPDATE = ''.join(e for e in date_modified if e.isalnum())
    return (FILE_UPDATE, LOCATION)

def get_local_file_mtime(addon):
    """Get mtime info for local file"""
    local_file = os.path.getmtime(ADDONS_DIR + addons["file"][addon])
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
    
    if addon in addons["projectSite"]["wowace"]:
        project_url = WOWACE_PROJECT_URL
    else:
        project_url = CURSEFORGE_PROJECT_URL

    project_webpage = requests.get(project_url + '/' + addon + '/files/' + location)
    project_webpage_text = html.fromstring(project_webpage.content)
    file_name = project_webpage_text.xpath('//div[@class="info-data overflow-tip"]/text()')[0]
    file_name = file_name.replace(' ', '%20')

    if len(location) == 6:
        location_1 = location[:3]
        location_2 = location[3:].lstrip("0")
    else:
        location_1 = location[:4]
        location_2 = location[4:].lstrip("0")

    download_url = CURSE_DOWNLOAD_URL + location_1 + '/' + location_2 + '/' + file_name
    r = requests.get(download_url, stream=True)
    with open('/tmp/' + file_name, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)

    
    #print download_url
    zip_ref = zipfile.ZipFile('/tmp/' + file_name, 'r')
    zip_ref.extractall(ADDONS_DIR)
    zip_ref.close()
    
    os.utime(ADDONS_DIR + addons["file"][addon], None)

def do_stuff(addon):
    """Iterate through the addon list, compare mtimes. 
    If local file is older than the one available for download, download and install.
    """
    FILE_UPDATE, LOCATION = check_for_update(addon)
#    num_retries = 6
#    sleep_time = 1
#
#    for x in range(0, num_retries):
#        try:
#            FILE_UPDATE, LOCATION = check_for_update(addon)
#            break
#        except IndexError as index_error:
#            pass
#
#        if index_error:
#            print "Error, retrying in %s second(s)" % sleep_time
#            sleep(sleep_time)
#            sleep_time *= 2
#        else:
#            break

    checked_addon = add_color.PURPLE + addons["file"][addon] + add_color.END_COLOR

    if FILE_UPDATE > get_local_file_mtime(addon):
        action = add_color.YELLOW + 'Downloading' + add_color.END_COLOR
        download_addon(addon, LOCATION)
    else:
        action = add_color.GREEN + 'Skipping' + add_color.END_COLOR    
    print "[ %s ]: %s" % (action, checked_addon)

def really_do_stuff():
    jobs = []
    for addon in addons["file"].keys():
        p = multiprocessing.Process(target=do_stuff, args=(addon,))
        jobs.append(p)
        p.start()

if __name__ == '__main__':
    really_do_stuff()
