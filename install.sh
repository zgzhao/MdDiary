#!/usr/bin/env bash

pip install -e .

DIR_CONFIG="$HOME/.MdDiary/assets"
[[ ! -d "$DIR_CONFIG" ]] && mkdir -p $DIR_CONFIG


cp -rf $PWD/assets/* $DIR_CONFIG/

DESKTOP_ENTRY="MdDiary.desktop"
MDIARY=`which mdiary`
echo "[Desktop Entry]" > $DESKTOP_ENTRY
echo "Type = Application" >> $DESKTOP_ENTRY
echo "Name = Markdown Diary" >> $DESKTOP_ENTRY
echo "Comment = Markdown日记" >> $DESKTOP_ENTRY
echo "Icon = $DIR_CONFIG/icon_app.png" >> $DESKTOP_ENTRY
echo "Terminal = false" >> $DESKTOP_ENTRY
echo "Exec = $MDIARY" >> $DESKTOP_ENTRY
echo "Categories = Office;" >> $DESKTOP_ENTRY

echo "Done."

