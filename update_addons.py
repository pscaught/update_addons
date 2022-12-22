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
from random import randint
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys

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


    def _chrome_setup(self):
        self.caps = DesiredCapabilities().CHROME
        self.caps['pageLoadStrategy'] = 'eager'
        self.chrome_options = Options()
        self.chrome_options.add_argument('--window-size=800,400')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--ignore-ssl-errors=yes')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--disable-accelerated-video-decode')
        self.chrome_options.set_capability('acceptInsecureCerts', True)
        self.chrome_options.add_experimental_option('prefs', { 'download_restrictions': 3, })
        self.browser = webdriver.Chrome(desired_capabilities=self.caps, options=self.chrome_options)
        self.url = f'{self.curse_url}{self.addon_url}/files/all?filter-game-version=1738749986%3A517&sort=releasetype'
        self.browser.get(self.url)

    def check_for_update(self, retry=0):
        """Parse the html of the Curse website for the timestamp and special location reference number of the latest
        file available for download"""

        try:
            while retry < 60:
                try:
                    self.webpage = self.browser.page_source
                    self.webpage_text = html.fromstring(self.webpage)
                    self.location = self.webpage_text.xpath('//*/table/tbody/tr[1]/td[2]/a/@href')[0].split('/')[-1]
                    break
                except:
                    if retry == 0:
                        self.browser.execute_script(f"window.open('{self.url}');")
                    time.sleep(1)
                    retry += 1
                    self.check_for_update(retry)
            else:
                raise IndexError

                
        except IndexError:
            print(Color.red, 
                  'Error fetching webpage data for {}.'.format(self.addon_url),
                  Color.end_color)
            self.file_update = None
            self.location = None
            return (None, None)

        epoch = self.webpage_text.xpath('//*/table/tbody/tr[1]/td[4]/abbr/@data-epoch')[0]
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

    def print_action(self):
        print('[ {} ]: {}'.format(self.action, self.checked_addon))


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
            location_2 = self.location[3:].lstrip('0')
        else:
            location_1 = self.location[:4]
            location_2 = self.location[4:].lstrip('0')


        download_url = '{}{}/{}/{}'.format(self.curse_download_url, location_1, location_2, file_)
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
        self.action = Color.green + 'Installed' + Color.end_color
        self.print_action()

    def do_stuff(self):
        """Iterate through the addon list, compare mtimes. 
        If local file is older than the one available for download, download and install.
        """
        self._chrome_setup()
        self.check_for_update()
        if None not in (self.file_update, self.location):
            self.checked_addon = Color.purple + self.addon_dir + Color.end_color

            if self.file_update > self.get_local_file_mtime():
                self.action = Color.yellow + 'Downloading' + Color.end_color
                self.print_action()
                self.download_addon()
            else:
                self.action = Color.green + 'Skipping' + Color.end_color    
                self.print_action()
        else:
            return



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

