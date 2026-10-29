"""Application release channel. Configure before building the first APK.

The GitHub repository must be public. GitHub source commits alone do not update
an Android installation: publish a signed APK as a GitHub Release asset.
"""

APP_VERSION = "0.4.0"
GITHUB_OWNER = "hermaer"      # Replace with your GitHub user if different.
GITHUB_REPOSITORY = "android-login-demo"  # Create this public repository.
