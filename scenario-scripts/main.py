from PyQt6.QtWidgets import QApplication, QMessageBox
from scenarioTool import ScenarioToolGUI
from version_checker import VersionChecker
import sys
import logging

def main():
    app = QApplication(sys.argv)
    
    # Check for updates
    checker = VersionChecker()
    has_update, update_url = checker.check_for_updates()
    
    if has_update:
        reply = QMessageBox.question(
            None, 
            'Update Available',
            'A new version is available. Would you like to update now?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            checker.download_update(update_url)
            return
    
    # Continue with normal startup
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()