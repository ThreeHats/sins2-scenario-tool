import requests
import json
from pathlib import Path
import sys
import os
import logging
from packaging import version

class VersionChecker:
    def __init__(self):
        self.github_api = "https://api.github.com/repos/ThreeHats/sins2-community-tools/releases/latest"
        self.current_version = "1.0.0"  # This will be updated during build
        self.app_dir = self._get_app_directory()
        
    def _get_app_directory(self):
        """Get the appropriate app directory based on whether we're frozen"""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        return Path(__file__).parent

    def _get_resource_path(self, resource_name: str) -> Path:
        """Get the appropriate path for a resource file"""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS) / resource_name
        return Path(__file__).parent / resource_name

    def check_for_updates(self):
        try:
            response = requests.get(self.github_api)
            response.raise_for_status()
            latest = response.json()
            
            latest_version = ''.join(c for c in latest['tag_name'] if c.isdigit() or c == '.')
            current_version = ''.join(c for c in self.current_version if c.isdigit() or c == '.')
            
            if version.parse(latest_version) > version.parse(current_version):
                return True, latest['assets'][0]['browser_download_url']
            return False, None
            
        except Exception as e:
            logging.error(f"Failed to check for updates: {e}")
            return False, None

    def download_update(self, url):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Use a more specific temp directory that we control
            temp_dir = Path(self.app_dir) / "temp"
            temp_dir.mkdir(exist_ok=True)
            update_path = temp_dir / "update.exe"
            
            with open(update_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Launch updater and exit current process
            os.startfile(update_path)
            try:
                temp_dir.unlink(missing_ok=True)
            except:
                pass
            sys.exit(0)
            
        except Exception as e:
            logging.error(f"Failed to download update: {e}")
            return False

    def download_community_files(self):
        """Download community files from GitHub repo"""
        base_url = "https://api.github.com/repos/ThreeHats/sins2-community-tools/contents/scenario-scripts/community"
        try:
            logging.info(f"Attempting to download community files from: {base_url}")
            response = requests.get(base_url)
            response.raise_for_status()
            contents = response.json()
            
            community_dir = self._get_app_directory() / "community"
            logging.info(f"Creating community directory at: {community_dir}")
            community_dir.mkdir(exist_ok=True)
            
            for item in contents:
                if item['type'] == 'dir':
                    logging.info(f"Found directory: {item['name']}")
                    self._download_directory(item['url'], community_dir / item['name'])
                else:
                    logging.info(f"Skipping non-directory item: {item['name']}")
                    
        except Exception as e:
            logging.error(f"Failed to download community files: {e}", exc_info=True)

    def _download_directory(self, url: str, target_dir: Path):
        """Recursively download directory contents"""
        try:
            logging.info(f"Downloading directory from {url} to {target_dir}")
            response = requests.get(url)
            response.raise_for_status()
            contents = response.json()
            
            target_dir.mkdir(exist_ok=True)
            
            for item in contents:
                if item['type'] == 'dir':
                    logging.info(f"Found subdirectory: {item['name']}")
                    self._download_directory(item['url'], target_dir / item['name'])
                else:
                    logging.info(f"Downloading file: {item['name']}")
                    self._download_file(item['download_url'], target_dir / item['name'])
                
        except Exception as e:
            logging.error(f"Failed to download directory {url}: {e}", exc_info=True)

    def _download_file(self, url: str, target_path: Path):
        """Download a single file"""
        try:
            logging.info(f"Downloading file from {url} to {target_path}")
            response = requests.get(url)
            response.raise_for_status()
            target_path.write_bytes(response.content)
            logging.info(f"Successfully downloaded: {target_path.name}")
        except Exception as e:
            logging.error(f"Failed to download file {url}: {e}", exc_info=True)