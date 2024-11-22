import sys
import json
import zipfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QListWidget, QFileDialog, QHBoxLayout, QLineEdit)
from PyQt6.QtCore import Qt, QMimeData, QFileSystemWatcher
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class ScenarioTool:
    def __init__(self):
        # Base directories
        self.output_dir = Path("output")
        
        # User and community directories
        self.user_dir = Path("user")
        self.community_dir = Path("community")
        
        # Template directories
        self.templates_dirs = {
            'user': self.user_dir / "templates",
            'community': self.community_dir / "templates"
        }
        
        # Script directories
        self.script_dirs = {
            'user': {
                'chart': self.user_dir / "scripts/chart",
                'generator': self.user_dir / "scripts/generator"
            },
            'community': {
                'chart': self.community_dir / "scripts/chart",
                'generator': self.community_dir / "scripts/generator"
            }
        }
        
        # Working directories stay the same
        self.working_dirs = {
            'chart': Path("working/chart"),
            'generator': Path("working/generator")
        }
        
        # Create all necessary directories
        for directory in [self.output_dir, *self.working_dirs.values()]:
            directory.mkdir(parents=True, exist_ok=True)
            
        for templates_dir in self.templates_dirs.values():
            for type_dir in ['chart', 'generator']:
                (templates_dir / type_dir).mkdir(parents=True, exist_ok=True)
                
        for scripts in self.script_dirs.values():
            for script_dir in scripts.values():
                script_dir.mkdir(parents=True, exist_ok=True)
        
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
    
    def load_template(self, template_name: str, source: str = 'user', expected_type: str = None) -> tuple[bool, str]:
        """Load a predefined template into working directory"""
        logging.debug(f"Loading template: name={template_name}, source={source}, expected_type={expected_type}")
        
        # Remove .scenario extension if present
        template_name = template_name.replace('.scenario', '')
        
        # Search in all type directories
        templates_dir = self.templates_dirs[source]
        for type_dir in ['chart', 'generator']:
            template_path = templates_dir / type_dir / f"{template_name}.scenario"
            logging.debug(f"Looking for template at: {template_path}")
            
            if template_path.exists():
                try:
                    # Check type before extracting
                    detected_type = self.determine_scenario_type(template_path)
                    message = ""
                    
                    if detected_type != type_dir:
                        logging.warning(f"Template type mismatch: found in {type_dir} but is {detected_type}")
                        # Try to relocate the template
                        new_path, reloc_message = self.relocate_template(template_path, detected_type)
                        message = reloc_message
                        if new_path:
                            template_path = new_path
                            logging.info("Template relocated successfully")
                        else:
                            logging.warning("Failed to relocate template, continuing with original location")
                    
                    # Extract template
                    result = self.extract_scenario(template_path)
                    if result:
                        logging.debug(f"Template loaded successfully as {detected_type} type")
                        return True, message
                    else:
                        logging.error("Failed to extract template")
                        return False, "Failed to extract template"
                except Exception as e:
                    logging.error(f"Error loading template: {e}", exc_info=True)
                    return False, f"Error loading template: {str(e)}"
        
        logging.error(f"Template not found: {template_name}")
        return False, f"Template not found: {template_name}"
    
    def save_as_template(self, template_name: str) -> bool:
        """Save the current scenario as a template"""
        if not self.current_type:
            print("No scenario loaded")
            return False
        
        try:
            # Create template directory if it doesn't exist
            template_dir = self.templates_dirs[self.current_type]
            template_dir.mkdir(parents=True, exist_ok=True)
            
            # Save directly as .scenario file
            template_path = template_dir / f"{template_name}.scenario"
            if template_path.exists():
                print(f"A template with this name already exists: {template_name}")
                return False
            
            # Create scenario file directly in template directory
            return self.create_scenario(template_name, template_path.parent)
            
        except Exception as e:
            print(f"Error saving template: {e}")
            return False
    
    def relocate_template(self, template_path: Path, correct_type: str) -> tuple[Path | None, str]:
        """Move template to the correct type directory"""
        # Construct new path
        new_path = template_path.parent.parent / correct_type / template_path.name
        message = f"Moving template from {template_path.parent.name} to {correct_type} folder"
        logging.debug(f"Relocating template from {template_path} to {new_path}")
        
        try:
            # Create directory if it doesn't exist
            new_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the file
            if new_path.exists():
                message = f"Cannot move template: already exists in {correct_type} folder"
                logging.warning(f"Template already exists at destination: {new_path}")
                return None, message
            
            template_path.rename(new_path)
            logging.info(f"Successfully relocated template to {new_path}")
            return new_path, message
        except Exception as e:
            message = f"Failed to move template: {str(e)}"
            logging.error(f"Failed to relocate template: {e}")
            return None, message

class ScenarioToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.scenario_tool = ScenarioTool()
        self.init_ui()
        self.setup_file_watchers()
        
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
        self.update_template_list()
        layout.addWidget(QLabel('Available Templates:'))
        layout.addWidget(self.template_list)
        
        # Add directory selection
        dir_layout = QHBoxLayout()
        dir_label = QLabel('Save Directory:')
        self.dir_input = QLineEdit()
        self.dir_input.setText(str(self.scenario_tool.output_dir))
        self.dir_input.textChanged.connect(self.update_save_directory)
        self.dir_select_btn = QPushButton('Browse...')
        self.dir_select_btn.clicked.connect(self.select_directory)
        self.template_dir_btn = QPushButton('Save as Template')
        self.template_dir_btn.clicked.connect(self.save_as_template)
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_select_btn)
        dir_layout.addWidget(self.template_dir_btn)
        layout.addLayout(dir_layout)
        
        # Add name input
        name_layout = QHBoxLayout()
        name_label = QLabel('Scenario Name:')
        self.name_input = QLineEdit()
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Add directory buttons
        dir_buttons_layout = QHBoxLayout()
        
        steam_btn = QPushButton('Use Steam Scenarios Folder')
        steam_btn.clicked.connect(self.use_steam_directory)
        
        epic_btn = QPushButton('Use Epic Scenarios Folder')
        epic_btn.clicked.connect(self.use_epic_directory)
        
        default_btn = QPushButton('Use Default Output')
        default_btn.clicked.connect(self.use_default_directory)
        
        dir_buttons_layout.addWidget(steam_btn)
        dir_buttons_layout.addWidget(epic_btn)
        dir_buttons_layout.addWidget(default_btn)
        layout.addLayout(dir_buttons_layout)
        
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
            self.update_template_list()
    
    def run_script(self):
        if self.script_list.currentItem():
            script_name = self.script_list.currentItem().text()
            self.scenario_tool.apply_script(script_name)
    
    def load_template(self):
        if self.template_list.currentItem():
            full_name = self.template_list.currentItem().text()
            logging.debug(f"Loading template: {full_name}")
            
            try:
                # Handle both "source: name" and "source/type: name" formats
                if '/' in full_name:
                    source_type, name = full_name.split(': ')
                    source, expected_type = source_type.split('/')
                else:
                    source, name = full_name.split(': ')
                    expected_type = None
                
                logging.debug(f"Parsed template: source={source}, type={expected_type}, name={name}")
                
                # Load the template
                success, message = self.scenario_tool.load_template(name, source, expected_type)
                if success:
                    status = f'Loaded template: {name}'
                    if message:  # Add relocation message if present
                        status += f'\n{message}'
                    self.drop_label.setText(status)
                    self.save_scenario_btn.setEnabled(True)
                    # Update lists to reflect new type and possible relocation
                    self.update_template_list()
                    self.update_script_list()
                else:
                    self.drop_label.setText(message)
            except ValueError as e:
                self.drop_label.setText('Invalid template format')
                logging.error(f"Error parsing template name: {e}")
    
    def save_scenario(self):
        if not self.name_input.text():
            self.drop_label.setText('Please enter a scenario name')
            return
        
        output_path = self.scenario_tool.output_dir / f"{self.name_input.text()}.scenario"
        if output_path.exists():
            self.drop_label.setText('A scenario with this name already exists')
            return
        
        if self.scenario_tool.create_scenario(self.name_input.text()):
            self.drop_label.setText('Scenario saved successfully!')
    
    def update_script_list(self):
        """Update the list of available scripts"""
        self.script_list.clear()
        if self.scenario_tool.current_type:
            all_scripts = []
            # Get scripts from both user and community directories
            for source, scripts in self.scenario_tool.script_dirs.items():
                script_dir = scripts[self.scenario_tool.current_type]
                if script_dir.exists():
                    scripts = [f"{source}: {p.stem}" 
                              for p in script_dir.glob("*.py")
                              if p.stem != "__init__"]
                    all_scripts.extend(scripts)
            self.script_list.addItems(sorted(all_scripts))
    
    def select_directory(self):
        dir_name = QFileDialog.getExistingDirectory(
            self,
            "Select Save Directory",
            str(self.scenario_tool.output_dir)
        )
        if dir_name:
            self.dir_input.setText(dir_name)
            self.update_save_directory()
    
    def update_save_directory(self):
        new_dir = Path(self.dir_input.text())
        try:
            new_dir.mkdir(parents=True, exist_ok=True)
            self.scenario_tool.output_dir = new_dir
        except Exception as e:
            print(f"Error updating save directory: {e}")
    
    def use_steam_directory(self):
        steam_path = self.get_steam_scenarios_path()
        if steam_path.exists():
            self.dir_input.setText(str(steam_path))
            self.update_save_directory()
        else:
            self.drop_label.setText('Steam scenarios folder not found')
    
    def get_steam_scenarios_path(self):
        """Get the path to Steam's scenarios folder"""
        return Path.home() / "AppData" / "Local" / "sins2" / "drop_in_scenarios"
    
    def get_epic_scenarios_path(self):
        """Get the path to Epic's scenarios folder"""
        # Check all drives from C to Z
        for drive in (chr(i) + ':' for i in range(ord('C'), ord('Z')+1)):
            epic_path = Path(f"{drive}/Program Files/Epic Games/SinsOfASolarEmpire2/drop_in_scenarios")
            if epic_path.exists():
                return epic_path
        # Return default path if not found
        return Path("C:/Program Files/Epic Games/SinsOfASolarEmpire2/drop_in_scenarios")
    
    def use_epic_directory(self):
        epic_path = self.get_epic_scenarios_path()
        if epic_path.exists():
            self.dir_input.setText(str(epic_path))
            self.update_save_directory()
        else:
            self.drop_label.setText('Epic scenarios folder not found')
    
    def use_default_directory(self):
        self.dir_input.setText(str(Path("output")))
        self.update_save_directory()
    
    def save_as_template(self):
        if not self.name_input.text():
            self.drop_label.setText('Please enter a template name')
            logging.debug("Template save attempted without name")
            return
        
        if not self.scenario_tool.current_type:
            self.drop_label.setText('Please load a scenario first')
            logging.debug("Template save attempted without scenario loaded")
            return
        
        # Save to user templates directory
        template_path = (self.scenario_tool.templates_dirs['user'] / 
                        self.scenario_tool.current_type / 
                        f"{self.name_input.text()}.scenario")
        
        logging.debug(f"Attempting to save template to: {template_path}")
        
        if template_path.exists():
            self.drop_label.setText('A template with this name already exists')
            logging.debug(f"Template already exists at: {template_path}")
            return
        
        try:
            template_path.parent.mkdir(parents=True, exist_ok=True)
            if self.scenario_tool.create_scenario(template_path.stem, template_path.parent):
                self.drop_label.setText('Template saved successfully!')
                self.update_template_list()
                logging.debug("Template saved successfully")
        except Exception as e:
            self.drop_label.setText(f'Error saving template: {e}')
            logging.error(f"Error saving template: {e}", exc_info=True)
    
    def update_template_list(self):
        """Update the list of available templates"""
        self.template_list.clear()
        logging.debug("Updating template list")
        
        all_templates = []
        # Get templates from both user and community directories
        for source, templates_dir in self.scenario_tool.templates_dirs.items():
            # First, check for templates directly in templates directory
            for template in templates_dir.glob("*.scenario"):
                all_templates.append(f"{source}: {template.stem}")
            
            # Then check type subdirectories
            for type_dir in ['chart', 'generator']:
                type_path = templates_dir / type_dir
                if type_path.exists():
                    templates = [f"{source}/{type_dir}: {p.stem}" 
                               for p in type_path.glob("*.scenario")]
                    all_templates.extend(templates)
        
        logging.debug(f"Found all templates: {all_templates}")
        self.template_list.addItems(sorted(all_templates))
    
    def setup_file_watchers(self):
        """Setup watchers for scripts and templates directories"""
        self.watcher = QFileSystemWatcher()
        
        # Add script directories
        for scripts in self.scenario_tool.script_dirs.values():
            for script_dir in scripts.values():
                script_dir.mkdir(parents=True, exist_ok=True)
                self.watcher.addPath(str(script_dir))
        
        # Add template type directories
        for templates_dir in self.scenario_tool.templates_dirs.values():
            for type_dir in ['chart', 'generator']:
                (templates_dir / type_dir).mkdir(parents=True, exist_ok=True)
                self.watcher.addPath(str(templates_dir / type_dir))
        
        # Connect signals
        self.watcher.directoryChanged.connect(self.handle_directory_change)
    
    def handle_directory_change(self, path):
        """Handle changes in watched directories"""
        path = Path(path)
        logging.debug(f"Directory changed: {path}")
        if path.parent.name == "scripts":
            logging.debug("Updating script list due to directory change")
            self.update_script_list()
        elif path.parent.name == "templates":
            logging.debug("Updating template list due to directory change")
            self.update_template_list()

def main():
    app = QApplication(sys.argv)
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()