[app]

# App identity
title           = BWS Tracker
package.name    = bwstracker
package.domain  = com.bwstracker
version         = 1.0

# Source
source.dir          = .
source.include_exts = py,png,jpg,kv,atlas,db

# Python / Kivy
requirements = python3==3.11.6,kivy==2.3.0,reportlab,pillow

# Orientation
orientation = portrait

# Fullscreen (0 = show status bar)
fullscreen = 0

# Android icon + presplash (place your own 512x512 PNG as icon.png)
# android.icon           = icon.png
# android.presplash      = presplash.png
# android.presplash_color = #2B6CB0

[buildozer]
log_level  = 2
warn_on_root = 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ANDROID
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[buildozer:android]

android.minapi        = 21
android.api           = 34
android.ndk           = 25b
android.ndk_api       = 21

# Build both 64-bit and 32-bit ARM
android.archs         = arm64-v8a, armeabi-v7a

# Permissions needed for file export to Downloads
android.permissions   = \
    android.permission.WRITE_EXTERNAL_STORAGE, \
    android.permission.READ_EXTERNAL_STORAGE,  \
    android.permission.MANAGE_EXTERNAL_STORAGE

# Allow builds without a connected device
android.skip_update   = False
android.accept_sdk_license = True

# Release signing (fill in your own keystore details before publishing)
# android.release_artifact  = apk
# android.keystore          = bwstracker.keystore
# android.keystore_alias    = bwstracker
# android.keystore_passwd   = YOUR_PASSWORD
# android.keyalias_passwd   = YOUR_PASSWORD


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  iOS  (requires macOS + Xcode + Apple Developer account)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[buildozer:ios]
ios.kivy_ios_url    = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_url  = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.10.0
