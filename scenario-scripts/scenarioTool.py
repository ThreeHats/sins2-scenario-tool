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
        # Base directories
        self.output_dir = Path("output")
        self.templates_dir = Path("templates")
        
        # Separate working and script directories for each type
        self.working_dirs = {
            'chart': Path("working/chart"),
            'generator': Path("working/generator")
        }
        self.script_dirs = {
            'chart': Path("scripts/chart"),
            'generator': Path("scripts/generator")
        }
        
        # Create all necessary directories
        for directory in [self.output_dir, self.templates_dir, *self.working_dirs.values(), *self.script_dirs.values()]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Expected files in a scenario
        self.required_files = [
            "galaxy_chart.json",
            "galaxy_chart_fillings.json",
            "scenario_info.json"
        ]
        
        self.current_type = None  # Will store 'chart' or 'generator'
    
    def determine_scenario_type(self, scenario_path: Path) -> str:
        """Determine if this is a chart or generator scenario"""
        with zipfile.ZipFile(scenario_path, 'r') as zip_ref:
            files = zip_ref.namelist()
            if "galaxy_chart_generator_params.json" in files:
                return 'generator'
            elif "galaxy_chart.json" in files:
                return 'chart'
        return None
    
    def extract_scenario(self, scenario_path: Path) -> bool:
        """Extract .scenario file to appropriate working directory"""
        try:
            # Determine scenario type
            self.current_type = self.determine_scenario_type(scenario_path)
            if not self.current_type:
                print("Unknown scenario type")
                return False
            
            # Clear working directory
            working_dir = self.working_dirs[self.current_type]
            for file in working_dir.glob("*"):
                file.unlink()
            
            # Extract files
            with zipfile.ZipFile(scenario_path, 'r') as zip_ref:
                zip_ref.extractall(working_dir)
            
            return True
        except Exception as e:
            print(f"Error extracting scenario: {e}")
            return False
    
    def apply_script(self, script_name: str) -> bool:
        """Apply a script from the appropriate directory"""
        if not self.current_type:
            print("No scenario loaded")
            return False
            
        try:
            script_path = self.script_dirs[self.current_type] / f"{script_name}.py"
            if not script_path.exists():
                print(f"Script not found: {script_path}")
                return False
            
            # Import and run the script
            import importlib.util
            spec = importlib.util.spec_from_file_location(script_name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'transform_scenario'):
                module.transform_scenario(self.working_dirs[self.current_type])
                return True
            else:
                print(f"Script {script_name} does not have a transform_scenario function")
                return False
            
        except Exception as e:
            print(f"Error applying script: {e}")
            return False
    
    def create_scenario(self, output_name: str, source_dir: Path = None) -> bool:
        """Create .scenario file from json files"""
        if source_dir is None:
            source_dir = self.working_dirs[self.current_type]
            
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
                    shutil.copy2(source, self.working_dirs[self.current_type] / file)
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
        self.drop_label = QLabel('Drop .scenario file here\nNo file loaded')
        self.drop_label.setObjectName("dropLabel")  # Set object name for CSS targeting
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setMinimumHeight(100)
        layout.addWidget(self.drop_label)
        
        # Create script list
        self.script_list = QListWidget()
        self.update_script_list()
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
        self.run_script_btn.setEnabled(False)  # Initially disabled
        layout.addWidget(self.run_script_btn)
        
        self.load_template_btn = QPushButton('Load Selected Template')
        self.load_template_btn.clicked.connect(self.load_template)
        layout.addWidget(self.load_template_btn)
        
        self.save_scenario_btn = QPushButton('Save Scenario')
        self.save_scenario_btn.clicked.connect(self.save_scenario)
        self.save_scenario_btn.setEnabled(False)  # Initially disabled
        layout.addWidget(self.save_scenario_btn)
        
        # Enable drop events
        self.setAcceptDrops(True)
        
        # Load stylesheet
        self.load_stylesheet()
        
    def load_stylesheet(self):
        try:
            style_path = Path("style.qss")
            if style_path.exists():
                with open(style_path, 'r') as f:
                    self.setStyleSheet(f.read())
            else:
                print("Warning: style.qss not found")
        except Exception as e:
            print(f"Error loading stylesheet: {e}")
    
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
            scenario_type = self.scenario_tool.current_type.capitalize()
            self.drop_label.setText(f'Loaded: {file_path.name}\nType: {scenario_type} Scenario')
            # Enable buttons
            self.run_script_btn.setEnabled(True)
            self.save_scenario_btn.setEnabled(True)
            # Update script list based on scenario type
            self.update_script_list()
    
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
    
    def update_script_list(self):
        """Update the list of available scripts based on current scenario type"""
        self.script_list.clear()
        if self.scenario_tool.current_type:
            scripts_dir = self.scenario_tool.script_dirs[self.scenario_tool.current_type]
            if scripts_dir.exists():
                for script_file in scripts_dir.glob("*.py"):
                    if script_file.stem != "__init__":
                        self.script_list.addItem(script_file.stem)

def main():
    app = QApplication(sys.argv)
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()