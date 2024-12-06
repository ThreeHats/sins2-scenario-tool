from PyQt6.QtWidgets import QApplication, QMessageBox
from scenarioTool import ScenarioToolGUI
from version_checker import VersionChecker
import sys
import logging

def main():
    app = QApplication(sys.argv)
    
    # Only download community files here
    checker = VersionChecker()
    checker.download_community_files()
    
    # Continue with normal startup
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()