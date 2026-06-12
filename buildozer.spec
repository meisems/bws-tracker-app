[app]

title           = BWS Tracker
package.name    = bwstracker
package.domain  = com.bwstracker
version         = 1.0

source.dir          = .
source.include_exts = py,png,jpg,kv,atlas

requirements = python3,kivy==2.3.0,reportlab

orientation = portrait
fullscreen  = 0

[buildozer]
log_level    = 2
warn_on_root = 1

[buildozer:android]
android.minapi             = 21
android.api                = 34
android.ndk                = 25b
android.ndk_api            = 21
android.archs              = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.permissions        = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
