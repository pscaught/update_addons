#!/usr/bin/env python3

import re
import sys
import yaml
import tkinter
from tkinter import filedialog

root = tkinter.Tk()
root.withdraw()

NEW_VALUES = ''

try:
    with open('config.yaml', 'r') as yaml_file:
        data = yaml.load(yaml_file, Loader=yaml.FullLoader)
except IOError:
    print('No config file found. Creating new one.')
    data = dict(dict(
        { 'addons': [] } 
        ))

try:
    data['addons_dir']
except KeyError:
    print('No primary addon dir found.')
    print('Select an addon ROOT directory.')
    root.update()
    data['addons_dir'] = filedialog.askdirectory()
    if [x for x in data['addons_dir'].split('/') if x][-1] != 'AddOns':
        raise Exception('This does not appear to be a valid addon directory!')
    NEW_VALUES = '\n' + 'addons_dir:' + ' ' + data['addons_dir']

print('Select an addon directory for the addon you are adding.')
root.update()
new_addon_dir = filedialog.askdirectory()
new_addon_dir = [x for x in new_addon_dir.split('/') if x][-1]
try:
    new_addon_url = input('Enter addon URL: ')
except KeyboardInterrupt:
    sys.exit(1)
new_addon_url = [x for x in new_addon_url.split('/') if x][-1]
try:
    for i in range(0, len(data['addons'])):
        if new_addon_dir in data['addons'][i]['dir']:
            raise Exception('Addon reference already in yaml file!')
        if new_addon_url in data['addons'][i]['url']:
            raise Exception('Addon reference already in yaml file!')
except KeyError:
    pass

NEW_VALUES = NEW_VALUES + '\n' + \
             'url:' + ' ' + new_addon_url + '\n' + \
             'dir:' + ' ' + new_addon_dir + '\n'
print(''.join(NEW_VALUES))

try:
    choice = input('Continue with writing these values?: ').lower()
except KeyboardInterrupt:
    sys.exit(1)

if choice in 'yes':
    print('Writing new values.')
elif choice in 'no':
    print('Not writing file.. exiting.')
    sys.exit(1)
else:
    print('Please respond with yes or no.')


data['addons'] += [ {
    'dir': new_addon_dir,
    'url': new_addon_url
    } ]

with open('config.yaml', 'w') as outfile:
    yaml.dump(data, outfile, default_flow_style=False, sort_keys=True)
