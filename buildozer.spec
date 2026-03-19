[app]

# (str) Title of your application
title = megaChess

# (str) Package name
package.name = megachess

# (str) Package domain (needed for android/ios packaging)
package.domain = org.adamsuk

# (str) Source code where the main.py live
source.dir = Chess

# (list) Source files to include (leave empty to include all in the project)
source.include_exts = py,png,jpg,kv,atlas,json,svg

# (str) Application versioning (method 1)
version = 0.1.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3==3.11.0,pygame

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 1

# (list) Permissions
android.permissions = INTERNET

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (int) Android NDK API to use. This is the minimum API your app will support,
# it should usually match android.minapi.
android.ndk_api = 21

# (str) The entry point of your application
# (str) Entrypoint of the application (module.Class)
# For pygame apps, the main python file to run
android.entrypoint = org.kivy.android.PythonActivity

# (list) Copy these files/dirs to the apk /assets folder (does not need source.dir prefix)
# android.add_assets =

# (str) python-for-android branch to use, defaults to master
#p4a.branch = master

# (str) Bootstrap to use for app
p4a.bootstrap = sdl2

# (str) Main python file for pygame/sdl2 bootstrap
android.main_file = game.py

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
