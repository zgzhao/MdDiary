import os

DIR_USER   = os.path.join(os.path.expanduser('~'), '.MdDiary')
DIR_DIARY  = os.path.join(DIR_USER, 'data')

DIR_ASSETS = os.path.join(DIR_USER, 'assets')
ICON_APP   = os.path.join(DIR_ASSETS, 'icon_app.png')

USER_CONFIG_FILE = os.path.join(DIR_ASSETS, "config.json")
USER_STYLES_FILE = os.path.join(DIR_ASSETS, "styles.css")
