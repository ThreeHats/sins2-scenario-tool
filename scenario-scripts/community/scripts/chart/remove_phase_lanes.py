import json
import logging
from pathlib import Path

def load_json(file_path):
    """Load JSON from file with error handling"""
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            logging.debug(f"Successfully loaded JSON from {file_path}")
            return data
    except Exception as e:
        logging.error(f"Error loading JSON from {file_path}: {str(e)}")
        raise

def save_json(data, file_path):
    """Save JSON to file with error handling"""
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
            logging.debug(f"Successfully saved JSON to {file_path}")
    except Exception as e:
        logging.error(f"Error saving JSON to {file_path}: {str(e)}")
        raise

def transform_scenario(working_dir):
    """Remove all phase lanes from the galaxy chart"""
    logging.info("Starting phase lane removal")
    
    try:
        # Load the galaxy chart
        galaxy_chart_path = working_dir / "galaxy_chart.json"
        galaxy_chart = load_json(galaxy_chart_path)
        
        # Count existing phase lanes
        original_count = len(galaxy_chart.get('phase_lanes', []))
        logging.info(f"Found {original_count} phase lanes to remove")
        
        # Remove all phase lanes
        galaxy_chart['phase_lanes'] = []
        
        # Save the modified chart
        save_json(galaxy_chart, galaxy_chart_path)
        logging.info(f"Successfully removed {original_count} phase lanes")
        
    except Exception as e:
        logging.error(f"Error during phase lane removal: {str(e)}", exc_info=True)
        raise