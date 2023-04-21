#!/usr/bin/env python

import datetime
import os
import multiprocessing
import pytz
import requests
import time
import yaml
import zipfile

from lxml import html
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

CURSE_URL = "https://www.curseforge.com/wow/addons/"
CURSE_DOWNLOAD_URL = "https://media.forgecdn.net/files/"
CURSEFORGE_PROJECT_URL = "https://wow.curseforge.com/projects/"
WOWACE_PROJECT_URL = "https://www.wowace.com/projects"
CONFIG_FILE = "config.yaml"

# Open local yaml config
with open(CONFIG_FILE) as addon_file:
    DATA = yaml.safe_load(addon_file)
ADDONS_DIR = DATA["addons_dir"] + "/"


# Colors!
class Color:
    purple = "\033[95m"
    blue = "\033[94m"
    green = "\033[92m"
    yellow = "\033[93m"
    red = "\033[91m"
    end_color = "\033[0m"
    bold = "\033[1m"
    underline = "\033[4m"


class CurseBrowser:
    """Open a Selenium browser designed to load the Curse webpage."""

    def __init__(self, addon):
        self.data = DATA
        self.addon = addon
        self.addon_url = self.addon["url"]
        self.dir = self.addon["dir"]
        self.project_id = self.addon.get("project_id")
        self.curse_url = CURSE_URL
        self.chrome_active = False

    def _chrome_setup(self):
        """Set Chrome options and open initial URL in browser"""
        self.caps = DesiredCapabilities().CHROME
        self.caps["pageLoadStrategy"] = "eager"
        self.chrome_options = Options()
        self.chrome_options.add_argument("--window-size=800,400")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )
        # self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--ignore-ssl-errors=yes")
        self.chrome_options.add_argument("--ignore-certificate-errors")
        # self.chrome_options.add_argument("--disable-accelerated-video-decode")
        self.chrome_options.set_capability("acceptInsecureCerts", True)
        self.chrome_options.add_experimental_option(
            "prefs",
            {
                "download_restrictions": 3,
            },
        )
        self.browser = webdriver.Chrome(
            desired_capabilities=self.caps, options=self.chrome_options
        )
        self.url = f"{self.curse_url}{self.addon_url}"
        self.browser.get(self.url)
        self.chrome_active = True

    def get_project_id(self, retry=0):
        """Parse the html of the Curse website for the project ID.
        Args: retry - used for retrying the parse
        Returns: A valid project ID or None if missing or errors
        """

        # If this method somehow got called when we have a valid project id,
        # simply return it
        if self.project_id:
            return self.project_id

        # Launch chrome
        if not self.chrome_active:
            self._chrome_setup()

        # Begin recursive retry loop, bail after 30 attempts
        if retry < 30:
            try:
                return (
                    html.fromstring(self.browser.page_source)
                    .xpath(
                        "/html/body/div[1]/main/div[2]/aside/div/section[1]/dl/dd[3]"
                    )[0]
                    .text
                )
            except IndexError:
                # Open page again in case Cloudflare does some random spot check
                if retry == 0:
                    self.browser.execute_script(f"window.open('{self.url}');")
                time.sleep(1)
                retry += 1
                self.check_for_update(retry)
                return None
        else:
            print(
                Color.red,
                "Error fetching webpage data for {}.".format(self.addon_url),
                Color.end_color,
            )
            return None


class Curse:
    """Using a given url path, directory name, and project ID, perform
    operations"""

    def __init__(self, addon):
        self.data = DATA
        self.addon = addon
        self.addon_url = self.addon["url"]
        self.dir = self.addon["dir"]
        self.project_id = self.addon["project_id"]
        self.addons_dir = ADDONS_DIR
        self.curse_download_url = CURSE_DOWNLOAD_URL

    def get_data(self):
        """Get modified time, filename, and file ID for latest addon available."""
        api_url = f"https://www.curseforge.com/api/v1/mods/{self.project_id}/files?pageSize=20&sort=dateCreated&sortDescending=true&removeAlphas=true&gameVersion=517"
        r = requests.get(api_url)
        if r.status_code == 200:
            data = r.json()["data"]
            for d in data:
                if d["releaseType"] == 1 and 517 in d["gameVersionTypeIds"]:
                    latest_release = d
                    break
            # Create a timezone object for UTC
            utc_timezone = pytz.timezone("UTC")

            # Create a timezone object for PST
            pst_timezone = pytz.timezone("US/Pacific")
            mtime_obj = datetime.datetime.strptime(
                latest_release["dateCreated"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            pst_mtime_obj = mtime_obj.replace(tzinfo=utc_timezone).astimezone(
                pst_timezone
            )

            self.mtime = pst_mtime_obj.strftime("%Y%m%d%H%M%S")
            self.filename = latest_release["fileName"]
            self.id = str(latest_release["id"])

        else:
            print("ERROR getting data")

    def get_local_file_mtime(self):
        """Get mtime info for local addon file"""
        try:
            local_file_mtime = os.path.getmtime(self.addons_dir + self.dir)
            return datetime.datetime.fromtimestamp(local_file_mtime).strftime(
                "%Y%m%d%H%M%S"
            )
        except FileNotFoundError:
            return "0"

    def download_addon(self):
        """Multi-step process to figure out the file name.
        Step 2) Using self.id we may build our actual download url (direct
            link to the file), and finally download the addon.
        Step 3) Addon file will be a .zip, so we unzip the file directly into
            the ADDONS_DIR
        """

        if len(self.id) == 6:
            location_1 = self.id[:3]
            location_2 = self.id[3:].lstrip("0")
        else:
            location_1 = self.id[:4]
            location_2 = self.id[4:].lstrip("0")

        download_url = "{}{}/{}/{}".format(
            self.curse_download_url, location_1, location_2, self.filename
        )
        r = requests.get(download_url, stream=True)
        with open("/tmp/" + self.filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        # print(download_url)
        zip_ref = zipfile.ZipFile("/tmp/" + self.filename, "r")
        zip_ref.extractall(self.addons_dir)
        zip_ref.close()

        os.utime(self.addons_dir + self.dir, None)
        self.action = Color.green + "Installed" + Color.end_color
        self.print_action()

    def do_stuff(self):
        """Compare whether the addon on Curse is more recent than the local one.
        Trigger a download and install if necessary."""
        self.get_data()
        if None not in (self.mtime, self.id):
            self.checked_addon = Color.purple + self.dir + Color.end_color
            if self.mtime > self.get_local_file_mtime():
                self.action = Color.yellow + "Downloading" + Color.end_color
                self.print_action()
                self.download_addon()
            else:
                self.action = Color.green + "Skipping" + Color.end_color
                self.print_action()
        else:
            return

    def print_action(self):
        """Formatting for status output"""
        print("[ {} ]: {}".format(self.action, self.checked_addon))


def check_addon(a):
    """Main function executed by multiprocessing"""
    if a["dir"] and a["url"] and a["project_id"]:
        c = Curse(a)
        c.do_stuff()
    else:
        print("ERROR: Missing data in config file.")


if __name__ == "__main__":
    write_data = False

    # Iterate through the config file
    for i, addon in enumerate(DATA["addons"]):
        # Original versions of the script didn't require project_id to be in
        # the config file, so we have some helper logic to retrieve and write it
        if not addon.get("project_id"):
            c = CurseBrowser(addon)
            write_data = True
            project_id = c.get_project_id()
            c.browser.quit()
            if project_id:
                DATA["addons"][i]["project_id"] = project_id
            else:
                print("Error getting project_id")
    if write_data:
        with open(CONFIG_FILE, "w") as addon_file:
            yaml.dump(DATA, addon_file, default_flow_style=False, sort_keys=True)

    processes = []
    for addon in DATA["addons"]:
        processes.append(multiprocessing.Process(target=check_addon, args=(addon,)))
    for p in processes:
        p.start()
