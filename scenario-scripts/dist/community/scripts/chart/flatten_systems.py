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
    """Save JSON to file with custom number formatting"""
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
            logging.debug(f"Successfully saved JSON to {file_path}")
    except Exception as e:
        logging.error(f"Error saving JSON to {file_path}: {str(e)}")
        raise

def transform_scenario(working_dir):
    """Flatten all solar systems into one root node"""
    logging.info("Starting system flattening")
    
    try:
        # Load the galaxy chart
        galaxy_chart_path = working_dir / "galaxy_chart.json"
        galaxy_chart = load_json(galaxy_chart_path)
        
        root_nodes = galaxy_chart['root_nodes']
        first_root_node = root_nodes[0]
        
        # Process additional root nodes (solar systems)
        logging.info(f"Found {len(root_nodes) - 1} additional solar systems to flatten")
        for node in root_nodes[1:]:
            logging.debug(f"Processing node {node['id']}")
            # Copy the star
            star_copy = node.copy()
            if 'child_nodes' in star_copy:
                del star_copy['child_nodes']
            star_copy['original_parent_id'] = 0
            star_copy['chance_of_retrograde_orbit'] = 0.0
            
            # Add all children to first root node
            if 'child_nodes' in node:
                for child in node['child_nodes']:
                    first_root_node['child_nodes'].append(child)
                
            # Add the star itself
            first_root_node['child_nodes'].append(star_copy)
        
        # Set single root node
        galaxy_chart['root_nodes'] = [first_root_node]
        logging.info(f"Flattened {len(root_nodes)} nodes into single root node")
        
        # Save the modified chart
        save_json(galaxy_chart, galaxy_chart_path)
        logging.info("Successfully saved flattened galaxy chart")
        
    except Exception as e:
        logging.error(f"Error during flattening: {str(e)}", exc_info=True)
        raise