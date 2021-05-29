#!/usr/bin/env python3

import multiprocessing
import os
import cfscrape
import yaml
import zipfile
from datetime import date
from lxml import html

cfscrape.DEFAULT_CIPHERS += ':!SHA1'
CURSE_URL = 'https://www.curseforge.com/wow/addons/'
CURSE_DOWNLOAD_URL = 'https://media.forgecdn.net/files/'
CURSEFORGE_PROJECT_URL = 'https://wow.curseforge.com/projects/'
WOWACE_PROJECT_URL = 'https://www.wowace.com/projects'
CONFIG_FILE = 'config.yaml'

# Open local yaml config
with open(CONFIG_FILE) as addon_file:
    data = yaml.load(addon_file, Loader=yaml.FullLoader)
ADDONS_DIR = data['addons_dir']

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

class Curse:
    def update_all(self):
        jobs = []
        for addon in range(0, len(data['addons'])):
            self.addon = addon
            self.addon_url = data['addons'][addon]['url']
            self.addon_dir = data['addons'][addon]['dir']
            p = multiprocessing.Process(target=self.check_addon)
            jobs.append(p)
            p.start()


    def check_for_update(self):
        """Parse the html of the Curse website for the timestamp and special location reference number of the latest
        file available for download"""
        s = cfscrape.create_scraper()

        webpage = s.get(CURSE_URL + self.addon_url + '/download')
        webpage_text = html.fromstring(webpage.content)
      
        location = webpage_text.xpath('//p[@class="text-sm"]/a/@href')[0].split('/')[-2]
        epoch = webpage_text.xpath('//*/abbr[@class="tip standard-date standard-datetime"]/@data-epoch')[0]
        epoch = float(epoch)
        date_modified = str(date.fromtimestamp(epoch))
        
        file_update = ''.join(e for e in date_modified if e.isalnum())

        return (file_update, location)

    def get_local_file_mtime(self):
        """Get mtime info for local file"""
        local_file = os.path.getmtime(os.path.join(ADDONS_DIR, self.addon_dir))
        date_modified = str(date.fromtimestamp(local_file))
        LOCAL_FILE_MTIME = ''.join(e for e in date_modified if e.isalnum())
        return LOCAL_FILE_MTIME

    def download_addon(self, location):
        """Multi-step process to figure out the file name. 
        Step 1) Construct our project site url, then parse the html, 
        which will reveal the addon file name. 
        Step 2) Using the paramaters from the previous HTML parses, we may build our
        actual download url (direct link to the file), and download the addon.
        Step 3) Addon file will be a .zip, so we unzip the file directly into the ADDONS_DIR
        """

        s = cfscrape.create_scraper()
        project_webpage = s.get(CURSE_URL + self.addon_url + '/files/' + location)
        project_webpage_text = html.fromstring(project_webpage.content)
        _file = project_webpage_text.xpath('//span[@class="text-sm"]/text()')[0]
        _file = _file.replace(' ', '%20')

        # Special 'location' ID used by curseforge. It is used in the path to
        # the direct file
        # Below we strip leading '0's from the returned values and segment the full 
        # location ID number into two pieces
        if len(location) == 6:
            location_1 = location[:3]
            location_2 = location[3:].lstrip('0')
        else:
            location_1 = location[:4]
            location_2 = location[4:].lstrip('0')

        # Build the direct link to the addon zip file
        download_url = CURSE_DOWNLOAD_URL + location_1 + '/' + location_2 + '/' + _file
        #download_url = CURSE_DOWNLOAD_URL + location + '/' + file
        # Download the file to /tmp/
        r = s.get(download_url, stream=True)
        with open('/tmp/' + _file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        # Extract downladed zip to the ADDONS_DIR 
        zip_ref = zipfile.ZipFile('/tmp/' + _file, 'r')
        zip_ref.extractall(ADDONS_DIR)
        zip_ref.close()

        # Update downloaded files modified time to curren, in order 
        # to avoid any false positives in the event the Addon updated
        # time on the curse page is more recent than the modified 
        # time stored in the file
        os.utime(os.path.join(ADDONS_DIR, self.addon_dir), None)

    def check_addon(self):
        """Compare modified times of the addon file available for download vs. 
        the local file stored on the machine running this script.. 
        If local file is older than the one available for download, download and install.
        """
        file_update, location = self.check_for_update()
        checked_addon = add_color.PURPLE + self.addon_dir + add_color.END_COLOR

        if file_update > self.get_local_file_mtime():
            action = add_color.YELLOW + 'Downloading' + add_color.END_COLOR
            self.download_addon(location)
        else:
            action = add_color.GREEN + 'Skipping' + add_color.END_COLOR    
        print('[ {} ]: {}'.format(action, checked_addon))

if __name__ == '__main__':
    curse = Curse()
    curse.update_all()
