import sys
import json
import zipfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QLabel, QListWidget, QFileDialog, QHBoxLayout, QLineEdit, QSizePolicy, QComboBox, QCheckBox, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea)
from PyQt6.QtCore import Qt, QMimeData, QFileSystemWatcher, QPointF, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen, QColor, QBrush
from scenarioOperations import Operation, Comparison, LogicalOp, Filter, FilterGroup, apply_operation
import logging
import time
from typing import Optional, List, Dict, Any

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
    
    def determine_scenario_type(self, template_name: str) -> Optional[str]:
        """Determine if this is a chart or generator scenario."""
        try:
            parts = template_name.split(': ')
            if len(parts) != 2:
                logging.error(f"Invalid template format: {template_name}")
                return None
            
            source, name = parts
            source_dir = self.templates_dirs.get(source.split('/')[0])
            if not source_dir:
                logging.error(f"Unknown source: {source}")
                return None
            
            # Construct the full path to the template
            template_path = source_dir / source.split('/')[1] / f"{name}.scenario"
            
            with zipfile.ZipFile(template_path, 'r') as zip_ref:
                files = zip_ref.namelist()
                if "galaxy_chart_generator_params.json" in files:
                    return 'generator'
                elif "galaxy_chart.json" in files:
                    return 'chart'
        except Exception as e:
            logging.error(f"Error determining scenario type: {str(e)}")
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
    
    def load_template(self, template_name: str) -> tuple[bool, str]:
        """Load a template by name."""
        try:
            # Determine the correct path based on the template name
            parts = template_name.split(': ')
            if len(parts) != 2:
                logging.error(f"Invalid template format: {template_name}")
                return False, "Invalid template format"
            
            source, name = parts
            source_dir = self.templates_dirs.get(source.split('/')[0])
            if not source_dir:
                logging.error(f"Unknown source: {source}")
                return False, "Unknown source"
            
            # Construct the full path to the template
            template_path = source_dir / source.split('/')[1] / f"{name}.scenario"
            
            if not template_path.exists():
                logging.error(f"Template not found: {template_name}")
                return False, f"Template not found: {template_name}"
            
            # Extract the template
            with zipfile.ZipFile(template_path, 'r') as zip_ref:
                zip_ref.extractall(self.working_dirs['chart'])
            
            logging.info(f"Loaded template: {template_name}")
            self.current_type = self.determine_scenario_type(template_name)
            return True, "Template loaded successfully"
        except Exception as e:
            logging.error(f"Error loading template: {str(e)}")
            return False, f"Error loading template: {str(e)}"
    
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
        
        # Open in full screen
        self.showMaximized()
    
    def init_ui(self):
        self.setWindowTitle('Sins 2 Scenario Tool')
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)  # Use horizontal layout for main content
        
        # Left side (options)
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        
        # Add all existing widgets to options_layout
        self.drop_label = QLabel('Drop .scenario file here\nNo file loaded')
        self.drop_label.setObjectName("dropLabel")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setMinimumHeight(100)
        options_layout.addWidget(self.drop_label)
        
        self.script_list = QListWidget()
        self.update_script_list()
        options_layout.addWidget(QLabel('Available Scripts:'))
        options_layout.addWidget(self.script_list)
        
        self.template_list = QListWidget()
        self.update_template_list()
        options_layout.addWidget(QLabel('Available Templates:'))
        options_layout.addWidget(self.template_list)
        
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
        options_layout.addLayout(dir_layout)
        
        name_layout = QHBoxLayout()
        name_label = QLabel('Scenario Name:')
        self.name_input = QLineEdit()
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        options_layout.addLayout(name_layout)
        
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
        options_layout.addLayout(dir_buttons_layout)
        
        self.run_script_btn = QPushButton('Run Selected Script')
        self.run_script_btn.clicked.connect(self.run_script)
        self.run_script_btn.setEnabled(False)
        options_layout.addWidget(self.run_script_btn)
        
        self.load_template_btn = QPushButton('Load Selected Template')
        self.load_template_btn.clicked.connect(self.load_template)
        options_layout.addWidget(self.load_template_btn)
        
        self.save_scenario_btn = QPushButton('Save Scenario')
        self.save_scenario_btn.clicked.connect(self.save_scenario)
        self.save_scenario_btn.setEnabled(False)
        options_layout.addWidget(self.save_scenario_btn)
        
        self.setAcceptDrops(True)
        
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setText("Ready")
        options_layout.addWidget(self.status_label)
        
        self.log_display = QListWidget()
        self.log_display.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        options_layout.addWidget(self.log_display)
        
        self.log_handler = GUILogHandler(self.log_display)
        self.log_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(self.log_handler)
        
        self.script_list.itemSelectionChanged.connect(self.update_run_button_state)
        
        # Operation Controls
        operation_group = QWidget()
        operation_layout = QVBoxLayout(operation_group)

        operation_line = QHBoxLayout()
        self.operation_combo = QComboBox()
        self.operation_combo.addItems([op.value for op in Operation])
        self.target_property = QLineEdit()
        self.target_property.setPlaceholderText("property to change")
        self.operation_value = QLineEdit()
        self.operation_value.setPlaceholderText("new value")
        
        self.operation_combo.currentTextChanged.connect(self.update_operation_placeholders)
        
        operation_line.addWidget(self.operation_combo)
        operation_line.addWidget(self.target_property)
        operation_line.addWidget(QLabel("to"))
        operation_line.addWidget(self.operation_value)
        operation_layout.addLayout(operation_line)

        self.where_clauses_widget = QWidget()
        self.where_clauses_layout = QVBoxLayout(self.where_clauses_widget)
        operation_layout.addWidget(self.where_clauses_widget)

        add_where_btn = QPushButton("Add WHERE Clause")
        add_where_btn.clicked.connect(self.add_where_clause)
        operation_layout.addWidget(add_where_btn)

        self.apply_operation_btn = QPushButton("Apply Operation")
        self.apply_operation_btn.clicked.connect(self.apply_operation)
        operation_layout.addWidget(self.apply_operation_btn)

        options_layout.addWidget(operation_group)
        
        # Right side (galaxy viewer)
        self.galaxy_viewer = GalaxyViewer(save_callback=self.save_galaxy_data)
        
        # Add both sides to main layout
        main_layout.addWidget(options_widget, 3)  # 30% width
        main_layout.addWidget(self.galaxy_viewer, 7)  # 70% width
        
        self.load_stylesheet()
    
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
                        
                        # Refresh the galaxy viewer with the updated data
                        if self.scenario_tool.current_type == 'chart':
                            chart_path = self.scenario_tool.working_dirs['chart'] / "galaxy_chart.json"
                            with open(chart_path, 'r') as f:
                                chart_data = json.load(f)
                            self.galaxy_viewer.set_data(chart_data)
                            self.galaxy_viewer.update()
                    
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
        """Load the selected template and update the galaxy viewer."""
        selected_items = self.template_list.selectedItems()
        if not selected_items:
            logging.error("No template selected")
            return

        template_name = selected_items[0].text()
        success, message = self.scenario_tool.load_template(template_name)

        if success:
            logging.info(f"Loaded template: {template_name}")
            self.status_label.setText("Template loaded successfully")
            self.drop_label.setText(f"Loaded template: {template_name}")
            
            # Determine scenario type
            scenario_type = self.scenario_tool.determine_scenario_type(template_name)
            
            if scenario_type == 'chart':
                # Load the galaxy map data
                galaxy_chart_path = self.scenario_tool.working_dirs['chart'] / "galaxy_chart.json"
                try:
                    with open(galaxy_chart_path, 'r') as file:
                        galaxy_data = json.load(file)
                        self.galaxy_viewer.set_data(galaxy_data)
                        logging.info("Galaxy map loaded into viewer")
                except Exception as e:
                    logging.error(f"Failed to load galaxy map: {str(e)}")
                    self.status_label.setText("Failed to load galaxy map")
            elif scenario_type == 'generator':
                # Display message for generator scenarios
                self.galaxy_viewer.clear_and_set_message("Generator view not supported")
                logging.info("Generator scenario loaded, view not supported")
            
            # Update available scripts
            self.update_script_list()
        else:
            logging.error(message)
            self.status_label.setText("Failed to load template")
    
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
        """Update the list of available scripts based on the loaded template."""
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
    
    def validate_value(self, value_str: str) -> tuple[Any, bool]:
        """Validate and convert a string input to the appropriate type.
        Returns (converted_value, is_valid)"""
        # Handle boolean values
        if value_str.lower() in ['true', 'false']:
            return value_str.lower() == 'true', True
        
        # Handle numeric values
        try:
            # Try integer first
            if value_str.isdigit() or (value_str.startswith('-') and value_str[1:].isdigit()):
                return int(value_str), True
            # Then try float
            return float(value_str), True
        except ValueError:
            # If not a number, return as string
            return value_str, True
    
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
            
            # Validate operation value
            op_value_str = self.operation_value.text()
            op_value, is_valid = self.validate_value(op_value_str)
            
            if not is_valid:
                self.drop_label.setText("Invalid operation value")
                logging.error(f"Invalid operation value: {op_value_str}")
                return
            
            logging.debug(f"Validated operation value: {op_value} (type: {type(op_value)})")
            
            # Additional validation for numeric operations
            if operation in [Operation.ADD, Operation.MULTIPLY, Operation.DIVIDE, Operation.SCALE]:
                if not isinstance(op_value, (int, float)):
                    self.drop_label.setText("Operation value must be a number")
                    logging.error("Operation value must be a number for this operation type")
                    return
            
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
                value_str = value_input.text()
                
                # Validate the filter value
                value, is_valid = self.validate_value(value_str)
                if not is_valid:
                    logging.warning(f"Invalid filter value: {value_str}")
                    continue
                
                logging.debug(f"Adding filter: {property_name} {comparison.value} {value}")
                filters.append(Filter(property_name, comparison, value))

        return FilterGroup(filters, LogicalOp.AND)
    
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

    def save_galaxy_data(self, data):
        """Save the galaxy data to the working directory"""
        try:
            chart_path = self.scenario_tool.working_dirs['chart'] / "galaxy_chart.json"
            with open(chart_path, 'w') as f:
                json.dump(data, f, indent=2)
            logging.debug("Saved galaxy data to working copy")
        except Exception as e:
            logging.error(f"Failed to save galaxy data: {e}")

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
    def __init__(self, parent=None, save_callback=None):
        super().__init__(parent)
        self.save_callback = save_callback  # Store the save function
        
        # Add visibility flags first
        self.show_grid = True
        self.show_orbits = True
        self.show_star_lanes = True
        self.show_wormhole_lanes = True
        self.show_regular_lanes = True
        
        # Initialize viewer properties
        self.data = None
        self.setMinimumSize(400, 400)
        self.zoom = 0.1
        self.center_offset = QPointF(0, 0)
        self.dragging = False
        self.last_pos = None
        self.node_positions = {}  # Cache for node positions
        self.parent_child_connections = []  # Cache for parent-child connections
        self.selected_node = None
        
        # Create main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create left side (viewer) container
        viewer_container = QWidget()
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create checkbox container
        checkbox_container = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_container)
        checkbox_layout.setContentsMargins(5, 5, 5, 0)
        
        # Create checkboxes
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.stateChanged.connect(self.toggle_grid)
        
        self.orbits_checkbox = QCheckBox("Show Orbits")
        self.orbits_checkbox.setChecked(True)
        self.orbits_checkbox.stateChanged.connect(self.toggle_orbits)
        
        self.star_lanes_checkbox = QCheckBox("Show Star Lanes")
        self.star_lanes_checkbox.setChecked(True)
        self.star_lanes_checkbox.stateChanged.connect(self.toggle_star_lanes)
        
        self.wormhole_lanes_checkbox = QCheckBox("Show Wormholes")
        self.wormhole_lanes_checkbox.setChecked(True)
        self.wormhole_lanes_checkbox.stateChanged.connect(self.toggle_wormhole_lanes)
        
        self.regular_lanes_checkbox = QCheckBox("Show Regular Lanes")
        self.regular_lanes_checkbox.setChecked(True)
        self.regular_lanes_checkbox.stateChanged.connect(self.toggle_regular_lanes)
        
        # Add checkboxes to layout
        checkbox_layout.addWidget(self.grid_checkbox)
        checkbox_layout.addWidget(self.orbits_checkbox)
        checkbox_layout.addWidget(self.star_lanes_checkbox)
        checkbox_layout.addWidget(self.wormhole_lanes_checkbox)
        checkbox_layout.addWidget(self.regular_lanes_checkbox)
        checkbox_layout.addStretch()
        
        # Add checkbox container to viewer layout
        viewer_layout.addWidget(checkbox_container)
        viewer_layout.addStretch()
        
        # Create right side (node info) container
        info_container = QWidget()
        info_container.setFixedWidth(250)
        info_container.setVisible(False)
        self.info_container = info_container
        
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 5, 5, 5)
        info_layout.setSpacing(0)
        
        # Create node info header
        info_header = QLabel("Node Details")
        info_header.setObjectName("nodeInfoHeader")
        info_layout.addWidget(info_header)

        # Add "Add Property" button at the bottom
        add_property_btn = QPushButton("Add Property")
        add_property_btn.setObjectName("addPropertyButton")
        add_property_btn.setFixedHeight(24)  # Make button thinner
        add_property_btn.clicked.connect(self._add_new_property)
        info_layout.addWidget(add_property_btn)
        
        # Create node info table
        self.node_info = QTableWidget()
        self.node_info.setObjectName("nodeInfo")
        self.node_info.setColumnCount(2)
        self.node_info.setHorizontalHeaderLabels(["Property", "Value"])
        self.node_info.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.node_info.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.node_info.verticalHeader().setVisible(False)
        self.node_info.setShowGrid(False)
        self.node_info.itemChanged.connect(self._on_property_changed)
        self.node_info.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.node_info.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.node_info.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.node_info.setContentsMargins(0, 0, 0, 0)  # Set margins to 0 for the table
        info_layout.addWidget(self.node_info)
        
        # Add stretch at the bottom of info layout
        info_layout.addStretch(1)
        
        # Add containers to main layout
        main_layout.addWidget(viewer_container, 1)
        main_layout.addWidget(info_container, 0)
    
    def toggle_grid(self, state):
        self.show_grid = bool(state)
        self.update()
        
    def toggle_orbits(self, state):
        self.show_orbits = bool(state)
        self.update()
        
    def toggle_star_lanes(self, state):
        self.show_star_lanes = bool(state)
        self.update()
        
    def toggle_wormhole_lanes(self, state):
        self.show_wormhole_lanes = bool(state)
        self.update()
        
    def toggle_regular_lanes(self, state):
        self.show_regular_lanes = bool(state)
        self.update()
    
    def draw_phase_lanes(self, painter):
        central_pos = self.node_positions.get('0', QPointF(0.0, 0.0))
        
        # Draw parent-child connections as circles
        if self.show_orbits:
            painter.setPen(QPen(QColor(255, 255, 0), 1/self.zoom))  # Yellow for parent-child
            
            # First, draw all connections involving the central star
            central_connections = [(p, c) for p, c in self.parent_child_connections if p == '0' or c == '0']
            for parent_id, child_id in central_connections:
                other_id = child_id if parent_id == '0' else parent_id
                other_pos = self.node_positions.get(other_id)
                if other_pos:
                    diff = other_pos - central_pos
                    radius = (diff.x()**2 + diff.y()**2)**0.5
                    if radius > 0:
                        painter.drawEllipse(central_pos, radius, radius)
            
            # Then draw all other connections
            for parent_id, child_id in self.parent_child_connections:
                if parent_id != '0' and child_id != '0':
                    parent_pos = self.node_positions.get(parent_id)
                    child_pos = self.node_positions.get(child_id)
                    if parent_pos and child_pos:
                        diff = parent_pos - child_pos
                        radius = (diff.x()**2 + diff.y()**2)**0.5
                        if radius > 0:
                            painter.drawEllipse(parent_pos, radius, radius)
        
        # Draw phase lanes by type
        if 'phase_lanes' in self.data:
            for line in self.data['phase_lanes']:
                line_type = line.get('type', 'default')
                
                # Skip if this type is not visible
                if (line_type == 'star' and not self.show_star_lanes or
                    line_type == 'wormhole' and not self.show_wormhole_lanes or
                    line_type == 'default' and not self.show_regular_lanes):
                    continue
                
                node_a_pos = self.node_positions.get(str(line['node_a']), central_pos if str(line['node_a']) == '0' else None)
                node_b_pos = self.node_positions.get(str(line['node_b']), central_pos if str(line['node_b']) == '0' else None)
                
                if node_a_pos is not None and node_b_pos is not None:
                    # Set line style based on type
                    if line_type == 'wormhole':
                        painter.setPen(QPen(QColor(128, 0, 128), 2/self.zoom))  # Purple for wormholes
                    elif line_type == 'star':
                        painter.setPen(QPen(QColor(255, 215, 0), 2/self.zoom))  # Thicker gold for star connections
                    else:
                        painter.setPen(QPen(QColor(0, 0, 255), 1/self.zoom))  # Blue for default
                    
                    painter.drawLine(node_a_pos, node_b_pos)
    
    def set_data(self, data):
        self.data = data
        self.node_positions.clear()
        self.parent_child_connections.clear()
        if self.data and 'root_nodes' in self.data:
            self._collect_node_positions()
        self.update()

    def clear_and_set_message(self, message):
        self.data = None
        self.message = message
        self.update()
        
    def _collect_node_positions(self):
        def collect_positions(node):
            if 'id' in node and 'position' in node:
                node_id = str(node['id'])  # Convert ID to string
                pos = QPointF(node['position'][0], -node['position'][1] if node['position'][1] != -0.0 else 0.0)
                self.node_positions[node_id] = pos
                
                if 'child_nodes' in node:
                    for child in node['child_nodes']:
                        if 'id' in child and 'position' in child:
                            connection = (node_id, str(child['id']))
                            self.parent_child_connections.append(connection)
                        collect_positions(child)
        
        self.node_positions.clear()
        self.parent_child_connections.clear()
        
        # Process all nodes, including root nodes
        for node in self.data['root_nodes']:
            collect_positions(node)
    
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
            
            # Draw everything
            self.draw_grid(painter)
            self.draw_phase_lanes(painter)
            self.draw_nodes(painter)
            
            # Highlight selected node
            if self.selected_node:
                node_id = str(self.selected_node.get('id', ''))
                if node_id in self.node_positions:
                    pos = self.node_positions[node_id]
                    painter.setPen(QPen(QColor(255, 255, 255), 2/self.zoom))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(pos, 15/self.zoom, 15/self.zoom)
            
        finally:
            painter.end()
        
    def draw_grid(self, painter):
        if not self.show_grid:
            return
            
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
            pos = self.node_positions.get(str(node['id']), QPointF(0.0, 0.0))
            
            # Set node appearance based on type
            node_size = 10  # Reduced base node size
            if 'filling_name' in node:
                if 'star' in node['filling_name']:
                    color = QColor(255, 255, 0)  # Yellow for stars
                    node_size = 15  # Slightly larger for stars
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
        if event.button() == Qt.MouseButton.RightButton:
            self.dragging = True
            self.last_pos = event.pos()
        elif event.button() == Qt.MouseButton.LeftButton:
            # Convert screen coordinates to world coordinates
            screen_pos = event.pos()
            world_pos = self.screen_to_world(screen_pos)
            self.select_node_at_position(world_pos)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.dragging = False
    
    def mouseMoveEvent(self, event):
        if self.dragging and self.last_pos is not None:
            # Calculate the difference in position
            delta = event.pos() - self.last_pos
            self.center_offset += QPointF(delta.x(), delta.y())
            self.last_pos = event.pos()
            self.update()  # Redraw the view
    
    def screen_to_world(self, screen_pos):
        # Convert screen coordinates to world coordinates
        center = QPointF(self.width() / 2, self.height() / 2)
        # Convert QPoint to QPointF
        screen_pos_f = QPointF(screen_pos.x(), screen_pos.y())
        offset = screen_pos_f - center - self.center_offset
        return QPointF(offset.x() / self.zoom, offset.y() / self.zoom)
    
    def select_node_at_position(self, world_pos):
        closest_node = None
        closest_dist = float('inf')
        node_radius = 10 / self.zoom  # Adjust hit detection radius based on zoom
        
        # Search through all nodes
        for node_id, pos in self.node_positions.items():
            dx = pos.x() - world_pos.x()
            dy = pos.y() - world_pos.y()
            dist = (dx * dx + dy * dy) ** 0.5
            
            if dist < node_radius and dist < closest_dist:
                # Find the actual node data
                node_data = self.find_node_by_id(node_id)
                if node_data:
                    closest_node = node_data
                    closest_dist = dist
        
        # Update selected node and info display
        self.selected_node = closest_node
        self.update_node_info()
        self.update()
        
        # Debug logging
        if closest_node:
            logging.debug(f"Selected node: {closest_node.get('id', 'N/A')}")
        else:
            logging.debug("No node selected")
    
    def find_node_by_id(self, target_id):
        def search_nodes(node):
            if str(node.get('id', '')) == target_id:
                return node
            for child in node.get('child_nodes', []):
                result = search_nodes(child)
                if result:
                    return result
            return None
        
        if not self.data or 'root_nodes' not in self.data:
            return None
        
        for root_node in self.data['root_nodes']:
            result = search_nodes(root_node)
            if result:
                return result
        return None
    
    def update_node_info(self):
        if self.selected_node:
            # Disconnect itemChanged signal while updating
            self.node_info.itemChanged.disconnect(self._on_property_changed)
            
            # Clear existing items
            self.node_info.setRowCount(0)
            
            # Add basic info
            self._add_property_row("Node ID", str(self.selected_node.get('id', 'N/A')), editable=False)
            
            # Add position as separate X and Y coordinates (positive Y is up)
            if 'position' in self.selected_node:
                pos = self.selected_node['position']
                self._add_property_row("Position X", f"{pos[0]:.1f}")
                self._add_property_row("Position Y", f"{-pos[1]:.1f}")  # Display Y as negative
            
            # Add editable properties
            if 'filling_name' in self.selected_node:
                self._add_property_row("Type", self.selected_node['filling_name'])
            
            # Add other properties
            for key, value in self.selected_node.items():
                if key not in ['id', 'filling_name', 'position', 'child_nodes']:
                    self._add_property_row(key, str(value))
            
            # Show the container
            self.info_container.setVisible(True)
            
            # Reconnect itemChanged signal
            self.node_info.itemChanged.connect(self._on_property_changed)
            
            # Adjust height to content
            total_height = (self.node_info.rowHeight(0) * self.node_info.rowCount() + 
                          self.node_info.horizontalHeader().height() + 2)
            self.node_info.setFixedHeight(total_height)
            
            logging.debug(f"Updated node info table with {self.node_info.rowCount()} properties")
        else:
            self.info_container.setVisible(False)
            logging.debug("Cleared node info")

    def _add_property_row(self, key, value, editable=True):
        row = self.node_info.rowCount()
        self.node_info.insertRow(row)
        
        # Add key (always non-editable)
        key_item = QTableWidgetItem(key)
        key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.node_info.setItem(row, 0, key_item)
        
        # Add value
        value_item = QTableWidgetItem(value)
        if not editable:
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.node_info.setItem(row, 1, value_item)

    def _on_property_changed(self, item):
        if item.column() == 1:  # Value column
            row = item.row()
            key = self.node_info.item(row, 0).text()
            new_value = item.text()
            
            try:
                # Update the node data
                if key == "Type":
                    self.selected_node['filling_name'] = new_value
                    self.update()  # Redraw to update node color
                elif key == "Position X":
                    x = float(new_value)
                    self.selected_node['position'][0] = x
                    self.node_positions[str(self.selected_node['id'])] = QPointF(
                        x, -self.selected_node['position'][1]
                    )
                    self.update()
                elif key == "Position Y":
                    y = -float(new_value)
                    self.selected_node['position'][1] = y
                    self.node_positions[str(self.selected_node['id'])] = QPointF(
                        self.selected_node['position'][0], y
                    )
                    self.update()
                else:
                    # Try to convert to number if possible
                    try:
                        if '.' in new_value:
                            new_value = float(new_value)
                        else:
                            new_value = int(new_value)
                    except ValueError:
                        pass  # Keep as string if not a number
                    
                    self.selected_node[key] = new_value
                
                # Save changes using callback
                if self.save_callback:
                    self.save_callback(self.data)
                    logging.debug(f"Saved changes to working copy after updating {key}")
                else:
                    logging.warning("No save callback provided")
                
                logging.debug(f"Updated property {key} to {new_value}")
            except ValueError:
                # Restore the previous value if conversion fails
                if key in ["Position X", "Position Y"]:
                    pos = self.selected_node['position']
                    if key == "Position X":
                        item.setText(f"{pos[0]:.1f}")
                    else:
                        item.setText(f"{-pos[1]:.1f}")
                    logging.error(f"Invalid number format for {key}: {new_value}")

    def _add_new_property(self):
        if not self.selected_node:
            return
        
        # Add a new row with empty property
        row = self.node_info.rowCount()
        self.node_info.insertRow(row)
        
        # Add editable key
        key_item = QTableWidgetItem("new_property")
        self.node_info.setItem(row, 0, key_item)
        
        # Add editable value
        value_item = QTableWidgetItem("value")
        self.node_info.setItem(row, 1, value_item)
        
        # Update the selected node data
        self.selected_node["new_property"] = "value"
        
        # Calculate and set the table height based on content
        total_height = (self.node_info.rowHeight(0) * self.node_info.rowCount() + 
                       self.node_info.horizontalHeader().height() + 2)
        self.node_info.setFixedHeight(total_height)
        
        # Start editing the property name
        self.node_info.editItem(key_item)
        
        # Save changes
        if self.save_callback:
            self.save_callback(self.data)

def main():
    app = QApplication(sys.argv)
    window = ScenarioToolGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()