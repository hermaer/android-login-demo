@echo off
rem COPY this file to signing.local.bat and fill in YOUR local keystore settings.
rem NEVER commit signing.local.bat, *.jks or passwords to GitHub.
rem Use one signing key for all versions of the Android application.
set "FLET_ANDROID_SIGNING_KEY_STORE=C:\CHANGE_THIS\android-release-key.jks"
set "FLET_ANDROID_SIGNING_KEY_ALIAS=upload"
set "FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD=CHANGE_THIS"
set "FLET_ANDROID_SIGNING_KEY_PASSWORD=CHANGE_THIS"
