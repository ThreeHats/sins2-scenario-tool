import sys
import json
import zipfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QListWidget, QFileDialog, QHBoxLayout, QLineEdit, QSizePolicy, QComboBox)
from PyQt6.QtCore import Qt, QMimeData, QFileSystemWatcher, QPointF
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen, QColor, QBrush
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
        self.where_clauses = []  # Initialize the where_clauses list
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

        # Operation line
        operation_line = QHBoxLayout()
        self.operation_combo = QComboBox()
        self.operation_combo.addItems([op.value for op in Operation])
        self.target_property = QLineEdit()
        self.target_property.setPlaceholderText("property to change")
        self.operation_value = QLineEdit()
        self.operation_value.setPlaceholderText("new value")
        
        # Connect operation combo to update placeholders
        self.operation_combo.currentTextChanged.connect(self.update_operation_placeholders)
        
        operation_line.addWidget(self.operation_combo)
        operation_line.addWidget(self.target_property)
        operation_line.addWidget(QLabel("to"))
        operation_line.addWidget(self.operation_value)
        operation_layout.addLayout(operation_line)

        # WHERE clauses container
        self.where_clauses_widget = QWidget()
        self.where_clauses_layout = QVBoxLayout(self.where_clauses_widget)
        operation_layout.addWidget(self.where_clauses_widget)

        # Add WHERE clause button
        add_where_btn = QPushButton("Add WHERE Clause")
        add_where_btn.clicked.connect(self.add_where_clause)
        operation_layout.addWidget(add_where_btn)

        # Apply button
        self.apply_operation_btn = QPushButton("Apply Operation")
        self.apply_operation_btn.clicked.connect(self.apply_operation)
        operation_layout.addWidget(self.apply_operation_btn)

        layout.addWidget(operation_group)
        
        # Create horizontal split for main content
        main_layout = QHBoxLayout()
        
        # Left side (existing controls)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Move existing widgets to left layout
        # ... (move all existing widget additions to left_layout) ...
        
        # Right side (galaxy viewer)
        self.galaxy_viewer = GalaxyViewer()
        
        # Add both sides to main layout
        main_layout.addWidget(left_widget)
        main_layout.addWidget(self.galaxy_viewer)
        
        # Add main layout to central widget
        layout.addLayout(main_layout)
    
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
        
        # Update galaxy viewer if this is a chart scenario
        if self.scenario_tool.current_type == 'chart':
            try:
                chart_path = self.scenario_tool.working_dirs['chart'] / "galaxy_chart.json"
                with open(chart_path) as f:
                    chart_data = json.load(f)
                self.galaxy_viewer.set_data(chart_data)
            except Exception as e:
                logging.error(f"Error loading galaxy chart data: {e}")
    
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
            # Create filter group from WHERE clauses
            filter_group = self.get_filter_group()
            
            # Get operation parameters
            operation = Operation(self.operation_combo.currentText())
            logging.debug(f"Operation: {operation}")
            
            # For MOVE operation, target_property is the destination node ID
            if operation == Operation.MOVE:
                target_prop = self.operation_value.text()  # Use the value field as the target node ID
                logging.debug(f"Target node ID for move: {target_prop}")
            else:
                target_prop = self.target_property.text()
                logging.debug(f"Target property: {target_prop}")
            
            # Get operation value (not used for MOVE)
            op_value = self.operation_value.text()
            logging.debug(f"Initial operation value: {op_value}")
            
            try:
                if operation == Operation.MOVE:
                    op_value = int(op_value)
                    logging.debug(f"Using node ID: {op_value}")
                elif operation not in [Operation.REMOVE, Operation.CHANGE, Operation.ADD_PROPERTY]:
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
                target_property=str(op_value) if operation == Operation.MOVE else target_prop,  # Convert node ID to string
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
    
    def get_filter_group(self) -> FilterGroup:
        """Create a FilterGroup from the current WHERE clauses"""
        filters = []
        for clause_widget in self.where_clauses:
            # Get the input fields from the clause widget
            property_input = clause_widget.findChild(QLineEdit, name="filter_property")
            comparison_combo = clause_widget.findChild(QComboBox, name="comparison_combo")
            value_input = clause_widget.findChild(QLineEdit, name="filter_value")

            if property_input and comparison_combo and value_input:
                property_name = property_input.text()
                comparison = Comparison(comparison_combo.currentText())
                value = value_input.text()

                # Try to convert value to number if possible
                try:
                    value = float(value)
                except ValueError:
                    pass  # Keep as string if not a number

                filters.append(Filter(property_name, comparison, value))

        return FilterGroup(filters, LogicalOp.AND)  # Use AND to combine multiple conditions

    def add_where_clause(self):
        """Add a new WHERE clause to the filter"""
        clause_widget = QWidget()
        clause_layout = QHBoxLayout(clause_widget)

        # Filter property
        filter_property = QLineEdit()
        filter_property.setObjectName("filter_property")  # Add object name
        filter_property.setPlaceholderText("property")
        clause_layout.addWidget(filter_property)

        # Comparison operator
        comparison_combo = QComboBox()
        comparison_combo.setObjectName("comparison_combo")  # Add object name
        comparison_combo.addItems([comp.value for comp in Comparison])
        clause_layout.addWidget(comparison_combo)

        # Filter value
        filter_value = QLineEdit()
        filter_value.setObjectName("filter_value")  # Add object name
        filter_value.setPlaceholderText("value")
        clause_layout.addWidget(filter_value)

        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(lambda: self.remove_where_clause(clause_widget))
        clause_layout.addWidget(remove_btn)

        self.where_clauses_layout.addWidget(clause_widget)
        self.where_clauses.append(clause_widget)

    def remove_where_clause(self, clause_widget):
        """Remove a WHERE clause from the filter"""
        self.where_clauses.remove(clause_widget)
        clause_widget.deleteLater()

    def update_operation_placeholders(self):
        """Update input field placeholders based on selected operation"""
        operation = self.operation_combo.currentText()
        
        if operation == Operation.ADD_PROPERTY.value:
            self.target_property.setPlaceholderText("property to add")
            self.operation_value.setPlaceholderText("property value")
        elif operation == Operation.MOVE.value:
            self.target_property.setPlaceholderText("target node ID")
            self.operation_value.setPlaceholderText("unused")
        else:
            self.target_property.setPlaceholderText("property to change")
            self.operation_value.setPlaceholderText("new value")

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

class GalaxyViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.setMinimumSize(400, 400)
        self.zoom = 0.01
        self.center_offset = QPointF(0, 0)
        self.dragging = False
        self.last_pos = None
        self.node_positions = {}  # Cache for node positions
        self.parent_child_connections = []  # Cache for parent-child connections
        
    def set_data(self, data):
        self.data = data
        self.node_positions.clear()
        self.parent_child_connections.clear()
        if self.data and 'root_nodes' in self.data:
            self._collect_node_positions()
        self.update()
        
    def _collect_node_positions(self):
        def collect_positions(node):
            if 'id' in node and 'position' in node:
                node_id = str(node['id'])  # Convert ID to string
                pos = QPointF(node['position'][0], -node['position'][1])
                self.node_positions[node_id] = pos
                logging.debug(f"Collected position for node {node_id}: {pos.x()}, {pos.y()}")
                
                if 'child_nodes' in node:
                    for child in node['child_nodes']:
                        if 'id' in child and 'position' in child:
                            self.parent_child_connections.append((node_id, str(child['id'])))
                        collect_positions(child)
        
        self.node_positions.clear()
        self.parent_child_connections.clear()
        
        # Process all nodes, including root nodes
        for node in self.data['root_nodes']:
            collect_positions(node)
        
        # Verify final positions
        logging.debug(f"Total nodes collected: {len(self.node_positions)}")
        central_pos = self.node_positions.get('0')  # Use string key
        logging.debug(f"Final central star position: {central_pos.x() if central_pos else 'None'}, {central_pos.y() if central_pos else 'None'}")
    
    def paintEvent(self, event):
        if not self.data:
            return
            
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Set up the coordinate system
            painter.translate(self.width() / 2 + self.center_offset.x(),
                            self.height() / 2 + self.center_offset.y())
            painter.scale(self.zoom, self.zoom)
            
            # Draw grid
            self.draw_grid(painter)
            
            # Draw phase lanes
            self.draw_phase_lanes(painter)
            
            # Draw nodes
            self.draw_nodes(painter)
            
        finally:
            painter.end()
    
    def draw_phase_lanes(self, painter):
        # Retrieve the central star position with a default value
        central_pos = self.node_positions.get(0, QPointF(0.0, 0.0))  # Use integer key
        logging.debug(f"Using central star position: {central_pos.x()}, {central_pos.y()}")

        # Ensure central_pos is valid before using it
        if central_pos is not None:
            # Proceed with drawing logic using central_pos
            # Example: painter.drawLine(central_pos, some_other_pos)
            pass
        else:
            logging.warning("Central star position is None, using default (0.0, 0.0)")
            central_pos = QPointF(0.0, 0.0)
        
        # Draw parent-child connections first
        painter.setPen(QPen(QColor(255, 255, 0), 1/self.zoom))  # Yellow for parent-child
        for parent_id, child_id in self.parent_child_connections:
            parent_pos = self.node_positions.get(parent_id, central_pos if parent_id == '0' else None)
            child_pos = self.node_positions.get(child_id, central_pos if child_id == '0' else None)
            if parent_pos and child_pos:
                painter.drawLine(parent_pos, child_pos)
        
        # Then draw phase lanes
        if 'phase_lanes' in self.data:
            for line in self.data['phase_lanes']:
                node_a_pos = self.node_positions.get(str(line['node_a']), central_pos if str(line['node_a']) == '0' else None)
                node_b_pos = self.node_positions.get(str(line['node_b']), central_pos if str(line['node_b']) == '0' else None)
                
                if node_a_pos and node_b_pos:
                    # Set line style based on type
                    line_type = line.get('type', 'default')
                    if line_type == 'wormhole':
                        painter.setPen(QPen(QColor(128, 0, 128), 2/self.zoom))  # Purple for wormholes
                    elif line_type == 'star':
                        painter.setPen(QPen(QColor(255, 215, 0), 2/self.zoom))  # Thicker gold for star connections
                    else:
                        painter.setPen(QPen(QColor(0, 0, 255), 1/self.zoom))  # Blue for default
                    
                    painter.drawLine(node_a_pos, node_b_pos)
    
    def draw_grid(self, painter):
        # Draw coordinate grid
        grid_size = 1000  # Game units between grid lines
        grid_count = 10   # Number of grid lines in each direction
        
        painter.setPen(QPen(QColor(200, 200, 200), 1/self.zoom))
        
        for i in range(-grid_count, grid_count + 1):
            # Vertical lines
            painter.drawLine(i * grid_size, -grid_count * grid_size,
                           i * grid_size, grid_count * grid_size)
            # Horizontal lines
            painter.drawLine(-grid_count * grid_size, i * grid_size,
                           grid_count * grid_size, i * grid_size)
        
        # Draw axes
        painter.setPen(QPen(QColor(100, 100, 100), 2/self.zoom))
        painter.drawLine(-grid_count * grid_size, 0, grid_count * grid_size, 0)
        painter.drawLine(0, -grid_count * grid_size, 0, grid_count * grid_size)
        
    def draw_nodes(self, painter):
        if 'root_nodes' not in self.data:
            return
        
        # Create a flat list of all nodes first to avoid recursion issues
        all_nodes = []
        
        def collect_nodes(node):
            all_nodes.append(node)
            if 'child_nodes' in node:
                for child in node['child_nodes']:
                    collect_nodes(child)
        
        # Collect all nodes
        for node in self.data['root_nodes']:
            collect_nodes(node)
        
        # Draw all nodes
        for node in all_nodes:
            pos = QPointF(node['position'][0], -node['position'][1])
            
            # Set node appearance based on type
            node_size = 20  # Reduced base node size
            if 'filling_name' in node:
                if 'star' in node['filling_name']:
                    color = QColor(255, 255, 0)  # Yellow for stars
                    node_size = 40  # Slightly larger for stars
                elif 'planet' in node['filling_name']:
                    color = QColor(0, 255, 0)    # Green for planets
                elif 'asteroid' in node['filling_name']:
                    color = QColor(150, 150, 150) # Gray for asteroids
                else:
                    color = QColor(255, 255, 255) # White for others
            else:
                color = QColor(255, 255, 255)
            
            # Draw node
            painter.setPen(QPen(color.darker(), 2/self.zoom))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(pos, node_size/self.zoom, node_size/self.zoom)
    
    def wheelEvent(self, event):
        # Zoom in/out with mouse wheel
        factor = 1.2 if event.angleDelta().y() > 0 else 1/1.2
        self.zoom *= factor
        self.update()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.last_pos = event.pos()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
    
    def mouseMoveEvent(self, event):
        if self.dragging and self.last_pos:
            delta = event.pos() - self.last_pos
            self.center_offset += QPointF(delta.x(), delta.y())
            self.last_pos = event.pos()
            self.update()

def main():
    app = QApplication(sys.argv)
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()