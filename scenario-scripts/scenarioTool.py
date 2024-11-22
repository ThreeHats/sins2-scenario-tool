import json
import zipfile
import sys
import os
import shutil
from pathlib import Path

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

def main():
    if len(sys.argv) < 2:
        print("Usage: Drop a .scenario file onto this program")
        return
        
    scenario_path = Path(sys.argv[1])
    if not scenario_path.exists():
        print(f"File not found: {scenario_path}")
        return
        
    tool = ScenarioTool()
    
    # Example usage
    if tool.extract_scenario(scenario_path):
        # Here you could add menu-driven interface for different operations
        # For example:
        # 1. Apply specific scripts
        # 2. Create new scenario from working files
        # 3. Load templates
        pass

if __name__ == "__main__":
    main()