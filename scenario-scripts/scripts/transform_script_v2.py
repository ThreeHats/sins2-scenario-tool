import json
import os
import copy
import math

# Define file paths
original_file = r"""C:\\Users\\Noah\\AppData\\Local\\sins2\\drop_in_scenarios\\One of Everything0.6 - Copy\\galaxy_chart.json"""
directory = os.path.dirname(original_file)
new_json_file = os.path.join(directory, 'modified_galaxy_chart_v11.json')

# Load the original JSON
def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Save JSON to a file with custom number formatting
def round_near_zero(value, threshold=1e-10):
    return 0.0 if abs(value) < threshold else value

def save_json(data, file_path):
    def float_formatter(obj):
        if isinstance(obj, float):
            # Round very small numbers to 0 and format others normally
            rounded = round_near_zero(obj)
            return format(rounded, '.6f').rstrip('0').rstrip('.')
        return obj

    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, float):
                return float_formatter(obj)
            return super().default(obj)

    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4, cls=CustomJSONEncoder, ensure_ascii=False)

# Helper function to calculate distance
def calculate_distance(pos1, pos2):
    return sum((c1 - c2) ** 2 for c1, c2 in zip(pos1, pos2)) ** 0.5

# Load the JSON structure
galaxy_chart = load_json(original_file)
modified_chart = copy.deepcopy(galaxy_chart)
root_nodes = modified_chart['root_nodes']

# First root node processing
first_root_node = root_nodes[0]
additional_root_nodes = root_nodes[1:]

distance_reference = 5000  # Set fixed distance

def adjust_child_positions(children, old_parent_pos, new_parent_pos):
    for child in children:
        # Calculate relative position
        rel_x = child['position'][0] - old_parent_pos[0]
        rel_y = child['position'][1] - old_parent_pos[1]
        
        # Apply relative position to new parent position
        child['position'][0] = new_parent_pos[0] + rel_x
        child['position'][1] = new_parent_pos[1] + rel_y

def get_max_id(chart):
    max_id = 0
    for node in chart['root_nodes']:
        max_id = max(max_id, node['id'])
        for child in node.get('child_nodes', []):
            max_id = max(max_id, child['id'])
    for lane in chart.get('phase_lanes', []):
        max_id = max(max_id, lane['id'])
    return max_id

def process_root_nodes():
    # Get wormhole fixtures from root node
    root_wormholes = [child for child in first_root_node['child_nodes'] 
                      if child['filling_name'] == 'wormhole_fixture']
    
    # Get antimatter fountains and make sure they're preserved
    antimatter_fountains = [child for child in first_root_node['child_nodes'] 
                           if child['filling_name'] == 'random_antimatter_fountain_fixture']
    
    # Remove existing antimatter fountains from root node's children
    first_root_node['child_nodes'] = [child for child in first_root_node['child_nodes']
                                     if child['filling_name'] != 'random_antimatter_fountain_fixture']
    
    # Count stars from additional nodes
    stars = [node for node in additional_root_nodes if node['filling_name'] == 'random_star']
    
    # Initialize star_wormholes list
    star_wormholes = []
    
    # Calculate total objects to position
    total_objects = len(stars) + len(antimatter_fountains)
    angle_step = 360 / total_objects if total_objects > 0 else 0
    
    # Create a list of objects to position, alternating between fountains and stars
    objects_to_position = []
    for i in range(max(len(antimatter_fountains), len(stars))):
        if i < len(antimatter_fountains):
            objects_to_position.append(('fountain', antimatter_fountains[i]))
        if i < len(stars):
            objects_to_position.append(('star', stars[i]))
    
    # Process all objects
    for current_object, (obj_type, node) in enumerate(objects_to_position):
        angle = math.radians(current_object * angle_step)
        new_x = round_near_zero(distance_reference * math.cos(angle))
        new_y = round_near_zero(distance_reference * math.sin(angle))
        
        if obj_type == 'fountain':
            # Process antimatter fountain
            node['position'] = [new_x, new_y]
            node['orbit_speed_scalar'] = 10.0
            first_root_node['child_nodes'].append(node)
        else:
            # Process star
            old_pos = node['position']
            
            # Adjust positions of all child nodes and collect wormholes
            adjust_child_positions(node['child_nodes'], old_pos, [new_x, new_y])
            star_wormholes.extend([child for child in node['child_nodes'] 
                                 if child['filling_name'] == 'wormhole_fixture'])
            first_root_node['child_nodes'].extend(node['child_nodes'])
            
            # Add the star itself
            node_copy = copy.deepcopy(node)
            if 'child_nodes' in node_copy:
                del node_copy['child_nodes']
            node_copy['position'] = [new_x, new_y]
            node_copy['chance_of_retrograde_orbit'] = 0.0
            node_copy['original_parent_id'] = 0
            first_root_node['child_nodes'].append(node_copy)

    # Remove existing phase lanes connected to antimatter fountains
    antimatter_ids = {fountain['id'] for fountain in antimatter_fountains}
    modified_chart['phase_lanes'] = [
        lane for lane in modified_chart.get('phase_lanes', [])
        if lane['node_a'] not in antimatter_ids and lane['node_b'] not in antimatter_ids
    ]

    # Add new phase lanes between root wormholes and star wormholes
    next_id = get_max_id(modified_chart) + 1
    new_phase_lanes = []
    
    for i, root_wormhole in enumerate(root_wormholes):
        if i < len(star_wormholes):
            new_phase_lanes.append({
                'id': next_id + i,
                'node_a': root_wormhole['id'],
                'node_b': star_wormholes[i]['id'],
                'type': 'wormhole'
            })
    
    modified_chart['phase_lanes'].extend(new_phase_lanes)
    
    # Set the root_nodes to only contain the first node
    modified_chart['root_nodes'] = [first_root_node]

process_root_nodes()

# Save modified JSON
save_json(modified_chart, new_json_file)
