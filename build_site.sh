#!/bin/sh
# Puts the web page and the Python game logic together in _site/ (what GitHub Pages serves).
set -e
rm -rf _site
mkdir -p _site
cp -r web/. _site/
cp arcade.py _site/
touch _site/.nojekyll
