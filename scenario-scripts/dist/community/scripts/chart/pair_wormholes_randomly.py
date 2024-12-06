import json
import logging
from pathlib import Path
import random

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

def get_max_id(chart):
    """Get the highest ID used in the chart"""
    max_id = 0
    for node in chart['root_nodes']:
        max_id = max(max_id, node['id'])
        for child in node.get('child_nodes', []):
            max_id = max(max_id, child['id'])
    for lane in chart.get('phase_lanes', []):
        max_id = max(max_id, lane['id'])
    return max_id

def transform_scenario(working_dir):
    """Link wormholes randomly, ensuring each wormhole has at most one connection"""
    logging.info("Starting random wormhole linking")
    
    try:
        # Load the galaxy chart
        galaxy_chart_path = working_dir / "galaxy_chart.json"
        galaxy_chart = load_json(galaxy_chart_path)
        
        # Get all wormholes
        wormholes = []
        for node in galaxy_chart['root_nodes']:
            for child in node.get('child_nodes', []):
                if child['filling_name'] == 'wormhole_fixture':
                    wormholes.append(child)
        
        logging.info(f"Found {len(wormholes)} wormholes to link")
        
        # Create phase lanes for wormhole pairs
        next_id = get_max_id(galaxy_chart) + 1
        new_phase_lanes = []
        unlinked_wormholes = wormholes.copy()
        
        while len(unlinked_wormholes) >= 2:
            # Pick two random wormholes
            wormhole_a = random.choice(unlinked_wormholes)
            unlinked_wormholes.remove(wormhole_a)
            wormhole_b = random.choice(unlinked_wormholes)
            unlinked_wormholes.remove(wormhole_b)
            
            new_phase_lanes.append({
                'id': next_id,
                'node_a': wormhole_a['id'],
                'node_b': wormhole_b['id'],
                'type': 'wormhole'
            })
            next_id += 1
            logging.debug(f"Linked wormholes {wormhole_a['id']} and {wormhole_b['id']}")
        
        if unlinked_wormholes:
            logging.info(f"One wormhole (ID: {unlinked_wormholes[0]['id']}) remains unlinked due to odd number of wormholes")
        
        # Add new phase lanes to chart
        galaxy_chart['phase_lanes'].extend(new_phase_lanes)
        logging.info(f"Added {len(new_phase_lanes)} wormhole connections")
        
        # Save the modified chart
        save_json(galaxy_chart, galaxy_chart_path)
        logging.info("Successfully saved linked wormholes")
        
    except Exception as e:
        logging.error(f"Error during wormhole linking: {str(e)}", exc_info=True)
        raise