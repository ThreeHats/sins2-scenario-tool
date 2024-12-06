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
    """Remove all solar systems except the first one and keep only its first planet range"""
    logging.info("Starting cleanup to keep only first solar system and first planet range")
    
    try:
        # Load the generator params
        params_path = working_dir / "galaxy_chart_generator_params.json"
        params = load_json(params_path)
        
        # Store counts for logging
        original_system_count = len(params.get('solar_systems', []))
        
        if not params.get('solar_systems'):
            logging.warning("No solar systems found in generator params")
            return
        
        # Keep only the first solar system
        first_system = params['solar_systems'][0]
        original_range_count = len(first_system.get('planet_ranges', []))
        
        # Keep only the first planet range and set its count to 1
        if first_system.get('planet_ranges'):
            first_range = first_system['planet_ranges'][0]
            first_range['count'] = [1, 1]  # Set to generate exactly one planet
            first_system['planet_ranges'] = [first_range]
        else:
            first_system['planet_ranges'] = []
            logging.warning("No planet ranges found in first solar system")
        
        params['solar_systems'] = [first_system]
        
        # Save the modified params
        save_json(params, params_path)
        logging.info(f"Successfully cleaned generator params:")
        logging.info(f"Removed {original_system_count - 1} solar systems")
        logging.info(f"Removed {original_range_count - 1 if original_range_count > 0 else 0} planet ranges")
        logging.info(f"Kept first solar system with 1 planet range")
        
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}", exc_info=True)
        raise