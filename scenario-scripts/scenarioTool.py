import sys
import json
import zipfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QListWidget, QFileDialog, QHBoxLayout, QLineEdit, QSizePolicy, QComboBox)
from PyQt6.QtCore import Qt, QMimeData, QFileSystemWatcher
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from scenarioOperations import Operation, Comparison, LogicalOp, Filter, FilterGroup, apply_operation
import logging
import time

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
            "galaxy_chart_fillings.json",
            "scenario_info.json"
        ]

        # ToDo: require galaxy_chart_generator_params.json for generator scenarios and galaxy_chart.json for chart scenarios
        
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
    
    def apply_script(self, script_name: str) -> tuple[bool, str, float]:
        """Apply a script from the appropriate directory. Returns (success, message, execution_time)"""
        if not self.current_type:
            msg = "No scenario loaded"
            logging.error(msg)
            return False, msg, 0
        
        import time
        start_time = time.time()
        
        try:
            # Remove any .py extension if present
            script_name = script_name.replace('.py', '')
            script_path = self.script_dirs['user'][self.current_type] / f"{script_name}.py"
            
            # If not found in user scripts, try community scripts
            if not script_path.exists():
                script_path = self.script_dirs['community'][self.current_type] / f"{script_name}.py"
            
            if not script_path.exists():
                msg = f"Script not found: {script_name}"
                logging.error(msg)
                return False, msg, 0
            
            logging.info(f"Running script: {script_name} from {script_path}")
            
            # Import and run the script in a controlled environment
            import importlib.util
            spec = importlib.util.spec_from_file_location(script_name, script_path)
            module = importlib.util.module_from_spec(spec)
            
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                msg = f"Error loading script {script_name}: {str(e)}"
                logging.error(msg, exc_info=True)
                return False, msg, time.time() - start_time
            
            if not hasattr(module, 'transform_scenario'):
                msg = f"Script {script_name} does not have a transform_scenario function"
                logging.error(msg)
                return False, msg, time.time() - start_time
            
            try:
                module.transform_scenario(self.working_dirs[self.current_type])
                execution_time = time.time() - start_time
                msg = f"Successfully applied script: {script_name} ({execution_time:.2f}s)"
                logging.info(msg)
                return True, msg, execution_time
            except Exception as e:
                msg = f"Error in script {script_name}: {str(e)}"
                logging.error(msg, exc_info=True)
                return False, msg, time.time() - start_time
            
        except Exception as e:
            msg = f"Unexpected error applying script: {str(e)}"
            logging.error(msg, exc_info=True)
            return False, msg, time.time() - start_time
    
    def create_scenario(self, output_name: str, source_dir: Path = None) -> bool:
        """Create .scenario file from json files"""
        if source_dir is None:
            source_dir = self.working_dirs[self.current_type]
            
        try:
            output_path = self.output_dir / f"{output_name}.scenario"
            
            # Define required files based on scenario type
            required_files = [
                "galaxy_chart_fillings.json",
                "scenario_info.json"
            ]
            
            # Add type-specific required file
            if self.current_type == 'generator':
                required_files.append("galaxy_chart_generator_params.json")
            elif self.current_type == 'chart':
                required_files.append("galaxy_chart.json")
            
            logging.debug(f"Creating {self.current_type} scenario with required files: {required_files}")
            
            with zipfile.ZipFile(output_path, 'w') as zip_ref:
                missing_files = []
                for file in required_files:
                    file_path = source_dir / file
                    if file_path.exists():
                        zip_ref.write(file_path, file)
                        logging.debug(f"Added file to scenario: {file}")
                    else:
                        missing_files.append(file)
                        logging.error(f"Missing required file: {file}")
                
                if missing_files:
                    logging.error(f"Failed to create scenario due to missing files: {missing_files}")
                    return False
                
            logging.info(f"Successfully created scenario at: {output_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error creating scenario: {str(e)}", exc_info=True)
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
        self.setWindowTitle("Scenario Tool")
        self.scenario_tool = ScenarioTool()
        self.init_ui()
        self.setup_file_watchers()
        self.update_template_list()
        self.update_script_list()
    
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
        
        # Add status label
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")  # For CSS styling
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setText("Ready")
        layout.addWidget(self.status_label)
        
        # Add log display
        self.log_display = QListWidget()
        # Make the log display stretch when the window is resized
        self.log_display.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.log_display)
        
        # Setup custom logging handler
        self.log_handler = GUILogHandler(self.log_display)
        self.log_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(self.log_handler)
        
        # Enable run button when script is selected
        self.script_list.itemSelectionChanged.connect(self.update_run_button_state)
        
        # Operation Controls
        operation_group = QWidget()
        operation_layout = QVBoxLayout(operation_group)

        # Operation line (e.g., "Add '2' to 'chance_of_loot'")
        operation_line = QHBoxLayout()
        self.operation_combo = QComboBox()
        self.operation_combo.addItems([op.value for op in Operation])
        self.operation_value = QLineEdit()
        self.operation_value.setPlaceholderText("value")
        operation_line.addWidget(self.operation_combo)
        operation_line.addWidget(QLabel("'"))
        operation_line.addWidget(self.operation_value)
        operation_line.addWidget(QLabel("' to"))
        self.target_property = QLineEdit()
        self.target_property.setPlaceholderText("target property")
        operation_line.addWidget(self.target_property)
        operation_layout.addLayout(operation_line)

        # WHERE line (e.g., "WHERE 'filling_name' equals 'random_star'")
        where_line = QHBoxLayout()
        where_line.addWidget(QLabel("WHERE"))
        self.filter_property = QLineEdit()
        self.filter_property.setPlaceholderText("property")
        self.comparison_combo = QComboBox()
        self.comparison_combo.addItems([comp.value for comp in Comparison])
        self.filter_value = QLineEdit()
        self.filter_value.setPlaceholderText("value")
        where_line.addWidget(self.filter_property)
        where_line.addWidget(self.comparison_combo)
        where_line.addWidget(self.filter_value)
        operation_layout.addLayout(where_line)

        # Apply button
        self.apply_operation_btn = QPushButton("Apply Operation")
        self.apply_operation_btn.clicked.connect(self.apply_operation)
        self.apply_operation_btn.setEnabled(False)  # Initially disabled
        operation_layout.addWidget(self.apply_operation_btn)

        layout.addWidget(operation_group)
    
    def update_run_button_state(self):
        """Enable run button only when a script is selected and a scenario is loaded"""
        self.run_script_btn.setEnabled(
            self.script_list.currentItem() is not None and 
            self.scenario_tool.current_type is not None
        )
    
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
        try:
            if self.scenario_tool.extract_scenario(file_path):
                scenario_type = self.scenario_tool.current_type.capitalize()
                self.drop_label.setText(f'Loaded: {file_path.name}\nType: {scenario_type} Scenario')
                
                # Enable buttons
                self.run_script_btn.setEnabled(True)
                self.save_scenario_btn.setEnabled(True)
                self.apply_operation_btn.setEnabled(True)  # Make sure this line is present
                
                # Update lists
                self.update_script_list()
                self.update_template_list()
                
                logging.info(f"Successfully loaded scenario: {file_path}")
            else:
                self.drop_label.setText('Error loading scenario')
                logging.error(f"Failed to load scenario: {file_path}")
        except Exception as e:
            self.drop_label.setText(f'Error: {str(e)}')
            logging.error(f"Error loading scenario: {str(e)}", exc_info=True)
    
    def run_script(self):
        if self.script_list.currentItem():
            full_script_name = self.script_list.currentItem().text()
            
            # Parse "source: script_name" format
            try:
                source, script_name = full_script_name.split(": ", 1)  # Split on first occurrence only
                logging.debug(f"Executing script from {source}: {script_name}")
                
                # Get the correct script directory
                script_dir = self.scenario_tool.script_dirs[source][self.scenario_tool.current_type]
                script_path = script_dir / f"{script_name}.py"
                
                # Update status before running
                self.status_label.setText(f"Running script: {script_name}...")
                self.status_label.setProperty("status", "running")
                self.style().unpolish(self.status_label)
                self.style().polish(self.status_label)
                
                # Disable controls during execution
                self.script_list.setEnabled(False)
                QApplication.processEvents()  # Force UI update
                
                try:
                    success, message, execution_time = self.scenario_tool.apply_script(script_name)
                    
                    if success:
                        status_msg = f"Script completed in {execution_time:.2f}s"
                        self.status_label.setProperty("status", "success")
                        self.drop_label.setText(f"{message}\nScenario updated successfully!")
                    else:
                        status_msg = f"Script failed after {execution_time:.2f}s"
                        self.status_label.setProperty("status", "error")
                        self.drop_label.setText(message)
                    
                    self.status_label.setText(status_msg)
                    
                except Exception as e:
                    self.status_label.setText("Script execution failed")
                    self.status_label.setProperty("status", "error")
                    self.drop_label.setText(f"Error running script: {str(e)}")
                    logging.error("Error in script execution", exc_info=True)
                
                finally:
                    # Re-enable controls
                    self.script_list.setEnabled(True)
                    self.style().unpolish(self.status_label)
                    self.style().polish(self.status_label)
                
            except ValueError as e:
                logging.error(f"Invalid script name format: {full_script_name}")
                self.drop_label.setText("Invalid script format")
    
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
    
    def apply_operation(self):
        logging.info("Apply operation button clicked")
        if not self.apply_operation_btn.isEnabled():
            logging.warning("Apply operation button is disabled")
            return
        
        try:
            # Get filter parameters
            property_name = self.filter_property.text()
            logging.debug(f"Filter property: {property_name}")
            
            comparison = Comparison(self.comparison_combo.currentText())
            logging.debug(f"Comparison: {comparison}")
            
            filter_value = self.filter_value.text()
            logging.debug(f"Initial filter value: {filter_value}")
            
            # Convert value to appropriate type
            try:
                filter_value = float(filter_value)
                logging.debug(f"Converted filter value to float: {filter_value}")
            except ValueError:
                logging.debug("Keeping filter value as string")
                pass
            
            # Create filter
            filter_group = FilterGroup([
                Filter(property_name, comparison, filter_value)
            ])
            logging.debug("Created filter group")
            
            # Get operation parameters
            operation = Operation(self.operation_combo.currentText())
            logging.debug(f"Operation: {operation}")
            
            target_prop = self.target_property.text()
            logging.debug(f"Target property: {target_prop}")
            
            # Get operation value
            op_value = self.operation_value.text()
            logging.debug(f"Initial operation value: {op_value}")
            
            try:
                op_value = float(op_value)
                logging.debug(f"Converted operation value to float: {op_value}")
            except ValueError:
                if operation not in [Operation.REMOVE, Operation.CHANGE]:
                    self.drop_label.setText("Operation value must be a number")
                    logging.error("Operation value must be a number for this operation type")
                    return
                logging.debug("Keeping operation value as string")
            
            # Check if scenario is loaded
            if not self.scenario_tool.current_type:
                self.drop_label.setText("Please load a scenario first")
                logging.error("No scenario loaded")
                return
            
            # Load the appropriate file based on scenario type
            if self.scenario_tool.current_type == 'chart':
                file_path = self.scenario_tool.working_dirs['chart'] / "galaxy_chart.json"
            else:
                file_path = self.scenario_tool.working_dirs['generator'] / "galaxy_chart_generator_params.json"
            
            logging.debug(f"Using file path: {file_path}")
            
            # Load, modify and save the file
            with open(file_path, 'r') as f:
                data = json.load(f)
                logging.debug("Successfully loaded JSON data")
            
            from scenarioOperations import apply_operation as apply_op
            modified_data = apply_op(
                data=data,
                operation=operation,
                target_property=target_prop,
                filter_group=filter_group,
                value=op_value
            )
            logging.debug("Successfully applied operation")
            
            with open(file_path, 'w') as f:
                json.dump(modified_data, f, indent=4)
                logging.debug("Successfully saved modified data")
            
            self.drop_label.setText("Operation applied successfully!")
            logging.info("Operation completed successfully")
            
        except Exception as e:
            self.drop_label.setText(f"Error applying operation: {str(e)}")
            logging.error(f"Error applying operation: {str(e)}", exc_info=True)

class GUILogHandler(logging.Handler):
    def __init__(self, log_widget):
        super().__init__()
        self.log_widget = log_widget
        
    def emit(self, record):
        msg = self.format(record)
        # Use different colors for different log levels
        color = {
            'DEBUG': 'gray',
            'INFO': 'black',
            'WARNING': 'orange',
            'ERROR': 'red',
            'CRITICAL': 'darkred'
        }.get(record.levelname, 'black')
        
        self.log_widget.addItem(msg)
        item = self.log_widget.item(self.log_widget.count() - 1)
        item.setForeground(Qt.GlobalColor.red if 'ERROR' in msg else Qt.GlobalColor.black)
        self.log_widget.scrollToBottom()

def main():
    app = QApplication(sys.argv)
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()