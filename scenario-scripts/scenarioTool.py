import sys
import json
import zipfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QListWidget, QFileDialog)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

class ScenarioTool:
    def __init__(self):
        self.working_dir = Path("working")
        self.output_dir = Path("output")
        self.templates_dir = Path("templates")
        
        # Ensure necessary directories exist
        for directory in [self.working_dir, self.output_dir, self.templates_dir]:
            directory.mkdir(exist_ok=True)
        
        # Expected files in a scenario
        self.required_files = [
            "galaxy_chart.json",
            "galaxy_chart_fillings.json",
            "scenario_info.json"
        ]
    
    def extract_scenario(self, scenario_path: Path) -> bool:
        """Extract .scenario file (zip) contents to working directory"""
        try:
            with zipfile.ZipFile(scenario_path, 'r') as zip_ref:
                zip_ref.extractall(self.working_dir)
            return True
        except Exception as e:
            print(f"Error extracting scenario: {e}")
            return False
    
    def create_scenario(self, output_name: str, source_dir: Path = None) -> bool:
        """Create .scenario file from json files"""
        if source_dir is None:
            source_dir = self.working_dir
            
        try:
            output_path = self.output_dir / f"{output_name}.scenario"
            with zipfile.ZipFile(output_path, 'w') as zip_ref:
                for file in self.required_files:
                    file_path = source_dir / file
                    if file_path.exists():
                        zip_ref.write(file_path, file)
                    else:
                        print(f"Missing required file: {file}")
                        return False
            return True
        except Exception as e:
            print(f"Error creating scenario: {e}")
            return False
    
    def apply_script(self, script_name: str) -> bool:
        """Apply a predefined modification script to the working files"""
        # This would be implemented based on your specific modification needs
        pass
    
    def load_template(self, template_name: str) -> bool:
        """Load a predefined template into working directory"""
        template_dir = self.templates_dir / template_name
        if not template_dir.exists():
            print(f"Template not found: {template_name}")
            return False
            
        try:
            for file in self.required_files:
                source = template_dir / file
                if source.exists():
                    shutil.copy2(source, self.working_dir / file)
            return True
        except Exception as e:
            print(f"Error loading template: {e}")
            return False

class ScenarioToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.scenario_tool = ScenarioTool()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Sins 2 Scenario Tool')
        self.setMinimumSize(800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create drop area
        self.drop_label = QLabel('Drop .scenario file here')
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #666;
                border-radius: 8px;
                padding: 20px;
                background: #f0f0f0;
            }
        """)
        self.drop_label.setMinimumHeight(100)
        layout.addWidget(self.drop_label)
        
        # Create script list
        self.script_list = QListWidget()
        self.script_list.addItems(['Script 1', 'Script 2', 'Script 3'])  # Placeholder scripts
        layout.addWidget(QLabel('Available Scripts:'))
        layout.addWidget(self.script_list)
        
        # Create template list
        self.template_list = QListWidget()
        self.template_list.addItems(['Template 1', 'Template 2'])  # Placeholder templates
        layout.addWidget(QLabel('Available Templates:'))
        layout.addWidget(self.template_list)
        
        # Create buttons
        self.run_script_btn = QPushButton('Run Selected Script')
        self.run_script_btn.clicked.connect(self.run_script)
        layout.addWidget(self.run_script_btn)
        
        self.load_template_btn = QPushButton('Load Selected Template')
        self.load_template_btn.clicked.connect(self.load_template)
        layout.addWidget(self.load_template_btn)
        
        self.save_scenario_btn = QPushButton('Save Scenario')
        self.save_scenario_btn.clicked.connect(self.save_scenario)
        layout.addWidget(self.save_scenario_btn)
        
        # Enable drop events
        self.setAcceptDrops(True)
        
        # Apply stylesheet
        self.apply_stylesheet()
        
    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0a3880;
            }
            QListWidget {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #0d47a1;
            }
            QListWidget::item:hover {
                background-color: #4b4b4b;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        for file_path in files:
            if file_path.endswith('.scenario'):
                self.handle_scenario_file(Path(file_path))
                break
    
    def handle_scenario_file(self, file_path: Path):
        if self.scenario_tool.extract_scenario(file_path):
            self.drop_label.setText(f'Loaded: {file_path.name}')
            # Enable buttons
            self.run_script_btn.setEnabled(True)
            self.save_scenario_btn.setEnabled(True)
    
    def run_script(self):
        if self.script_list.currentItem():
            script_name = self.script_list.currentItem().text()
            self.scenario_tool.apply_script(script_name)
    
    def load_template(self):
        if self.template_list.currentItem():
            template_name = self.template_list.currentItem().text()
            self.scenario_tool.load_template(template_name)
            self.drop_label.setText(f'Loaded template: {template_name}')
            self.save_scenario_btn.setEnabled(True)
    
    def save_scenario(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scenario",
            str(self.scenario_tool.output_dir),
            "Scenario Files (*.scenario)"
        )
        if file_name:
            output_name = Path(file_name).stem
            if self.scenario_tool.create_scenario(output_name):
                self.drop_label.setText('Scenario saved successfully!')

def main():
    app = QApplication(sys.argv)
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()