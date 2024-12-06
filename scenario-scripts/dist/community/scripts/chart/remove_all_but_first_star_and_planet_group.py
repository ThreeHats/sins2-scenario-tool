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
    """Remove everything except the first root star, its first child, and their connecting phase lane"""
    logging.info("Starting cleanup to keep first root star and first child")
    
    try:
        # Load the galaxy chart
        galaxy_chart_path = working_dir / "galaxy_chart.json"
        galaxy_chart = load_json(galaxy_chart_path)
        
        # Store counts for logging
        original_root_count = len(galaxy_chart.get('root_nodes', []))
        original_phase_lanes = len(galaxy_chart.get('phase_lanes', []))
        
        if not galaxy_chart.get('root_nodes'):
            logging.warning("No root nodes found in galaxy chart")
            return
        
        # Keep only the first root node
        first_root = galaxy_chart['root_nodes'][0]
        root_id = first_root['id']
        
        # Keep only the first child node if it exists
        original_children = len(first_root.get('child_nodes', []))
        if original_children > 0:
            first_child = first_root['child_nodes'][0]
            child_id = first_child['id']
            first_root['child_nodes'] = [first_child]
            
            # Find and keep only the phase lane connecting root to first child
            connecting_phase_lanes = [
                lane for lane in galaxy_chart.get('phase_lanes', [])
                if (lane['node_a'] == root_id and lane['node_b'] == child_id) or
                   (lane['node_a'] == child_id and lane['node_b'] == root_id)
            ]
            galaxy_chart['phase_lanes'] = connecting_phase_lanes[:1]  # Keep only the first matching phase lane
        else:
            first_root['child_nodes'] = []
            galaxy_chart['phase_lanes'] = []
            logging.info("No child nodes found in first root")
        
        # Reset the galaxy chart to contain only this node
        galaxy_chart['root_nodes'] = [first_root]
        
        # Save the modified chart
        save_json(galaxy_chart, galaxy_chart_path)
        logging.info(f"Successfully cleaned galaxy chart:")
        logging.info(f"Removed {original_root_count - 1} additional root nodes")
        logging.info(f"Removed {original_children - 1 if original_children > 0 else 0} additional child nodes")
        logging.info(f"Removed {original_phase_lanes - (1 if original_children > 0 else 0)} phase lanes")
        
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}", exc_info=True)
        raise