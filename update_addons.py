#!/usr/bin/env python

import copy
import datetime
import difflib
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

CURSE_URL = "https://www.curseforge.com"
CURSE_ADDON_URL = f"{CURSE_URL}/wow/addons/"
CURSE_DOWNLOAD_URL = "https://media.forgecdn.net/files/"
CONFIG_FILE = "config.yaml"

# Open local yaml config
with open(CONFIG_FILE) as f:
    FILE_DATA = yaml.safe_load(f)
ADDONS = FILE_DATA["addons"]
ADDONS_DIR = FILE_DATA["addons_dir"] + "/"


# Colors!
class Color:
    purple = "\033[95m"
    # blue = "\033[94m"
    green = "\033[92m"
    yellow = "\033[93m"
    red = "\033[91m"
    end_color = "\033[0m"
    # bold = "\033[1m"
    # underline = "\033[4m"


class CurseBrowser:
    """Open a Selenium browser designed to load the Curse webpage."""

    def __init__(self, addon):
        self.addon = addon
        self.addon_url = self.addon["url"]
        self.dir = self.addon["dir"]
        self.project_id = self.addon.get("project_id")
        self.curse_addon_url = CURSE_ADDON_URL
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
        self.url = f"{self.curse_addon_url}{self.addon_url}"
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
        if retry < 10:
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
                self.get_project_id(retry)
                return None
        else:
            print(
                Color.red
                + f"Error fetching webpage data for {self.addon_url}"
                + Color.end_color
            )
            return None


class Curse:
    """Using a given url path, directory name, and project ID, perform
    operations"""

    def __init__(self, addon):
        self.addon = addon
        self.addon_url = self.addon["url"]
        self.curse_url = CURSE_URL
        self.dir = self.addon["dir"]
        self.project_id = self.addon["project_id"]
        self.addons_dir = ADDONS_DIR
        self.curse_download_url = CURSE_DOWNLOAD_URL

    def get_data(self):
        """Get modified time, filename, and file ID for latest addon available."""
        self.mtime = None
        self.filename = None
        self.id = None
        latest_release = None

        data_error = (
                Color.red + f"Error getting data for {self.addon_url}" + Color.end_color
            )

        api_url = (
            f"{self.curse_url}/api/v1/mods/{self.project_id}/files"
            + "?pageSize=20"
            + "&sort=dateCreated"
            + "&sortDescending=true"
            + "&removeAlphas=true"
            + "&gameVersion=517"
        )
        r = requests.get(api_url)
        if r.status_code == 200:
            data = r.json()["data"]
            for d in data:
                if d["releaseType"] == 1 and 517 in d["gameVersionTypeIds"]:
                    latest_release = d
                    break
            if not latest_release:
                print(data_error)
                return
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
            print(data_error)
            return

    def get_local_file_mtime(self):
        """Get mtime info for local addon file"""
        try:
            local_file_mtime = os.path.getmtime(self.addons_dir + self.dir)
            return datetime.datetime.fromtimestamp(local_file_mtime).strftime(
                "%Y%m%d%H%M%S"
            )
        except FileNotFoundError:
            return 0

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
        if None not in (self.filename, self.mtime, self.id):
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
    c = Curse(a)
    c.do_stuff()


if __name__ == "__main__":
    write_data = False
    addons = copy.deepcopy(ADDONS)

    # Iterate through the config file
    for i in range(len(addons) - 1, -1, -1):
        # Original versions of the script didn't require project_id to be in
        # the config file, so we have some helper logic to retrieve and write it
        addon = addons[i]
        _dir = addon.get("dir", "missing")
        _url = addon.get("url", "missing")
        _project_id = addon.get("project_id")

        if "missing" in (_dir, _url):
            print(
                Color.red
                + "ERROR: Missing data in config file."
                + "\n"
                + f"dir: {_dir}"
                + "\n"
                + f"url: {_url}"
                + Color.end_color
            )
            del addons[i]
            continue

        if not _project_id:
            c = CurseBrowser(addon)
            project_id = c.get_project_id()
            c.browser.quit()
            if project_id:
                addons[i]["project_id"] = project_id
                write_data = True
            else:
                print(
                    Color.red + f"Error getting project_id for {_url}" + Color.end_color
                )
                del addons[i]
                continue
    if write_data:
        # Compare the before and after of the file contents
        yaml1 = yaml.dump(ADDONS).splitlines()
        yaml2 = yaml.dump(addons).splitlines()

        differ = difflib.context_diff(
            yaml1, yaml2, lineterm="", fromfile="Before", tofile="After"
        )
        diff = "\n".join(
            Color.green + f"{line}" + Color.end_color
            if line.startswith("+ ")
            else Color.red + f"{line}" + Color.end_color
            if line.startswith("- ")
            else line
            for line in differ
            if line.strip()
        )
        print("Changes have been made to the configuration data. Please review them below.")
        print(diff)
        answer = input("Write changes to config file? (yes/no): ")
        if answer.lower().startswith('y'):
            FILE_DATA["addons"] = addons
            with open(CONFIG_FILE, "w") as f:
                yaml.dump(FILE_DATA, f, default_flow_style=False, sort_keys=True)
            print("Changes written to config file.")
        else:
            print("Changes not written to config file.")

    processes = []
    for addon in addons:
       processes.append(multiprocessing.Process(target=check_addon, args=(addon,)))
    for p in processes:
       p.start()
