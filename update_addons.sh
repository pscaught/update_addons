#!/bin/bash

WINDOWS_HOME_PATH='/mnt/c/Users/scott'

cd "${WINDOWS_HOME_PATH}/update_addons"
source addon_env/bin/activate
./update_addons.py
deactivate

echo "Updating ElvUI"

cd "${WINDOWS_HOME_PATH}/elvui"
git checkout main >/dev/null
git reset --hard origin/main
git pull --rebase

echo "Updating AddOnSkins"

cd "${WINDOWS_HOME_PATH}/addonskins"
git checkout main >/dev/null
git reset --hard origin/main
git pull --rebase
git submodule update

sleep 1
