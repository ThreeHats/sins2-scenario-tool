import requests
import json
from pathlib import Path
import sys
import os
import logging
from packaging import version

class VersionChecker:
    def __init__(self):
        self.github_api = "https://api.github.com/repos/JustAnotherIdea/sins2-community-tools/releases/latest"
        self.current_version = "1.0.0"  # This will be updated during build
        self.app_dir = self._get_app_directory()
        
    def _get_app_directory(self):
        """Get the appropriate app directory based on whether we're frozen"""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS)
        return Path(__file__).parent

    def check_for_updates(self):
        try:
            response = requests.get(self.github_api)
            response.raise_for_status()
            latest = response.json()
            
            latest_version = latest['tag_name'].lstrip('v')
            if version.parse(latest_version) > version.parse(self.current_version):
                return True, latest['assets'][0]['browser_download_url']
            return False, None
            
        except Exception as e:
            logging.error(f"Failed to check for updates: {e}")
            return False, None

    def download_update(self, url):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            update_path = Path(self.app_dir) / "update.exe"
            with open(update_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Launch updater and exit current process
            os.startfile(update_path)
            sys.exit(0)
            
        except Exception as e:
            logging.error(f"Failed to download update: {e}")
            return False