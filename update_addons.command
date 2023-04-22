#!/bin/bash

cd ~/addon_test
source addon_env/bin/activate
./update_addons.py
deactivate

#echo "Updating ElvUI"
#
#cd ~/elvui
#git reset --hard origin/master
#git pull --rebase
#
#cd ~/addonskins
#git reset --hard origin/master
#git pull --rebase
#git submodule update
#
#sleep 1
