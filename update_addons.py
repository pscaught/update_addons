#!/usr/bin/env python

import multiprocessing
import os
import requests
import sys
import time
import yaml
import zipfile

from datetime import date
from lxml import html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities



CURSE_URL = 'https://www.curseforge.com/wow/addons/'
CURSE_DOWNLOAD_URL = 'https://media.forgecdn.net/files/'
CURSEFORGE_PROJECT_URL = 'https://wow.curseforge.com/projects/'
WOWACE_PROJECT_URL = 'https://www.wowace.com/projects'
CONFIG_FILE = 'config.yaml'

# Open local yaml config
with open(CONFIG_FILE) as addon_file:
    DATA = yaml.load(addon_file, Loader=yaml.FullLoader)
ADDONS_DIR = DATA['addons_dir'] + '/'

# Colors!
class Color:
    purple = '\033[95m'
    blue = '\033[94m'
    green = '\033[92m'
    yellow = '\033[93m'
    red = '\033[91m'
    end_color = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'


class Curse():
    def __init__(self, addon):
        self.data = DATA
        self.addon = addon
        self.addon_url = self.addon['url']
        self.addon_dir = self.addon['dir']
        self.addons_dir = ADDONS_DIR
        self.curse_url = CURSE_URL
        self.curse_download_url = CURSE_DOWNLOAD_URL

        self.caps = DesiredCapabilities().CHROME
        self.caps['pageLoadStrategy'] = 'eager'
        self.chrome_options = Options()
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.set_capability('acceptInsecureCerts', True)
        self.chrome_options.add_experimental_option('prefs', { 'download_restrictions': 3, })
        self.browser = webdriver.Chrome(desired_capabilities=self.caps, options=self.chrome_options)

    def check_for_update(self):
        """Parse the html of the Curse website for the timestamp and special location reference number of the latest
        file available for download"""
        url = '{}{}/download'.format(self.curse_url, self.addon_url)
        self.browser.get(url)
        webpage = self.browser.page_source
        webpage_text = html.fromstring(webpage)

        #print(html.tostring(webpage_text))
        try:
            self.location = webpage_text.xpath('//p[@class="text-sm"]/a/@href')[0].split('/')[-2]
        except IndexError:
            print(Color.red, 
                  'Error fetching webpage data for {}.'.format(self.addon_url),
                  Color.end_color)
            return (None, None)
        epoch = webpage_text.xpath('//*/abbr[@class="tip standard-date standard-datetime"]/@data-epoch')[0]
        epoch = float(epoch)
        date_modified = str(date.fromtimestamp(epoch))
        
        self.file_update = ''.join(e for e in date_modified if e.isalnum())


    def get_local_file_mtime(self):
        """Get mtime info for local file"""
        try:
            local_file = os.path.getmtime(self.addons_dir + self.addon_dir)
            date_modified = str(date.fromtimestamp(local_file))
            return ''.join(e for e in date_modified if e.isalnum())
        except FileNotFoundError:
            return '0'

    def download_addon(self):
        """Multi-step process to figure out the file name. 
        Step 1) Construct our project site url, 
        after vailidating whether the project is wowace or curseforge, 
        which will reveal the addon file name. 
        Step 2) Using the paramaters from the previous HTML parses, we may build our
        actual download url (link to the file), and download the addon.
        Step 3) Addon file will be a .zip, so we unzip the file directly into the ADDONS_DIR
        """
        url = '{}{}/files/{}'.format(self.curse_url, self.addon_url, self.location)
        self.browser.get(url)
        project_webpage = self.browser.page_source
        project_webpage_text = html.fromstring(project_webpage)

        file_ = project_webpage_text.xpath('//span[@class="text-sm"]/text()')[0]
        file_ = file_.replace(' ', '%20')

        if len(self.location) == 6:
            location_1 = self.location[:3]
            location_2 = self.location[3:].lstrip("0")
        else:
            location_1 = self.location[:4]
            location_2 = self.location[4:].lstrip("0")


        download_url = '{}{}/{}/{}'.format(CURSE_DOWNLOAD_URL, location_1, location_2, file_)
        r = requests.get(download_url, stream=True)
        with open('/tmp/' + file_, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        
        #print(download_url)
        zip_ref = zipfile.ZipFile('/tmp/' + file_, 'r')
        zip_ref.extractall(self.addons_dir)
        zip_ref.close()
        
        os.utime(self.addons_dir + self.addon_dir, None)

    def do_stuff(self):
        """Iterate through the addon list, compare mtimes. 
        If local file is older than the one available for download, download and install.
        """
        self.check_for_update()
        if None not in (self.file_update, self.location):
            checked_addon = Color.purple + self.addon_dir + Color.end_color

            if self.file_update > self.get_local_file_mtime():
                action = Color.yellow + 'Downloading' + Color.end_color
                self.download_addon()
            else:
                action = Color.green + 'Skipping' + Color.end_color    
            print('[ {} ]: {}'.format(action, checked_addon))
        else:
            return

def split(list_a, chunk_size):
    for i in range(0, len(list_a), chunk_size):
        yield list_a[i:i + chunk_size]


def check_addon(a):
    c = Curse(a)
    c.do_stuff()
    c.browser.quit()


if __name__ == '__main__':
    processes = []
    for addon in DATA['addons']:
        processes.append(multiprocessing.Process(target=check_addon, args=(addon,)))
    for p in processes:
        p.start()
        time.sleep(0.5)
    for p in processes:
        p.join()

