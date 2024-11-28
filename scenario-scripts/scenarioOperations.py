import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Union, Optional
from enum import Enum

class Operation(Enum):
    ADD = "add"
    CHANGE = "change"
    REMOVE = "remove"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    SCALE = "scale"
    MOVE = "move"
    ADD_PROPERTY = "add_property"

class Comparison(Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"

class LogicalOp(Enum):
    AND = "and"
    OR = "or"
    NAND = "nand"
    XOR = "xor"

class Filter:
    def __init__(self, property: str, comparison: Comparison, value: Any):
        self.property = property
        self.comparison = comparison
        self.value = value

    def evaluate(self, obj: Dict) -> bool:
        if self.property not in obj:
            return False
            
        target = obj[self.property]
        
        if self.comparison == Comparison.EQUALS:
            return target == self.value
        elif self.comparison == Comparison.NOT_EQUALS:
            return target != self.value
        elif self.comparison == Comparison.GREATER_THAN:
            return target > self.value
        elif self.comparison == Comparison.LESS_THAN:
            return target < self.value
        return False

class FilterGroup:
    def __init__(self, filters: List[Filter], logical_op: LogicalOp = LogicalOp.AND):
        self.filters = filters
        self.logical_op = logical_op

    def evaluate(self, obj: Dict) -> bool:
        results = [f.evaluate(obj) for f in self.filters]
        
        if self.logical_op == LogicalOp.AND:
            return all(results)
        elif self.logical_op == LogicalOp.OR:
            return any(results)
        elif self.logical_op == LogicalOp.NAND:
            return not all(results)
        elif self.logical_op == LogicalOp.XOR:
            return sum(results) == 1
        return False
        
def apply_operation(data: Dict, 
                   operation: Operation,
                   target_property: str,
                   filter_group: FilterGroup,
                   value: Any = None,
                   operator_adjustment: float = 1.0) -> Dict:
    """Apply operation to filtered objects in the data"""
    logging.info(f"Applying operation {operation} to property {target_property}")
    
    # Keep track of nodes to move and their new parent
    nodes_to_move = []
    target_node_ref = {'node': None}  # Use a dict to store reference
    
    def find_node_by_id(nodes: List[Dict], node_id: str) -> Optional[Dict]:
        """Find a node by its ID in the node tree"""
        for node in nodes:
            if str(node.get('id')) == node_id:
                target_node_ref['node'] = node  # Store reference to the actual node
                logging.debug(f"Found target node: {node}")
                return node
            if 'child_nodes' in node:
                result = find_node_by_id(node['child_nodes'], node_id)
                if result:
                    return result
        return None

    def remove_node_from_parent(nodes: List[Dict], node_id: str) -> bool:
        """Remove a node from its current parent's child_nodes"""
        for i, node in enumerate(nodes):
            if str(node.get('id')) == node_id:
                nodes.pop(i)
                return True
            if 'child_nodes' in node:
                if remove_node_from_parent(node['child_nodes'], node_id):
                    return True
        return False

    def process_value(current_value: Any) -> Any:
        if operation == Operation.ADD:
            return current_value + (value * operator_adjustment)
        elif operation == Operation.MULTIPLY:
            return current_value * (value * operator_adjustment)
        elif operation == Operation.DIVIDE:
            return current_value / (value * operator_adjustment)
        elif operation == Operation.SCALE:
            return current_value * operator_adjustment
        elif operation == Operation.CHANGE:
            return value
        return current_value

    def process_object(obj: Dict) -> Optional[Dict]:
        if not isinstance(obj, dict):
            return obj
            
        # Check if this object matches our filter
        if filter_group.evaluate(obj):
            logging.debug(f"Found matching object: {obj}")
            if operation == Operation.REMOVE:
                logging.debug("Removing object")
                return None
            elif operation == Operation.MOVE:
                nodes_to_move.append(obj)
                logging.debug(f"Marked node {obj.get('id')} for moving")
                return None
            elif operation == Operation.ADD_PROPERTY:
                if target_property not in obj:
                    result = obj.copy()
                    result[target_property] = value
                    logging.debug(f"Added property {target_property} with value {value}")
                    return result
                return obj
            elif target_property in obj:
                result = obj.copy()
                current_value = obj[target_property]
                result[target_property] = process_value(current_value)
                logging.debug(f"Modified {target_property} from {current_value} to {result[target_property]}")
                return result
        
        # If not moving or removing, process children
        result = obj.copy()
        if 'child_nodes' in result:
            result['child_nodes'] = process_list(result['child_nodes'])
        return result

    def process_list(lst: List) -> List:
        result = []
        for item in lst:
            if isinstance(item, dict):
                processed = process_object(item)
                if processed is not None:
                    result.append(processed)
            elif isinstance(item, list):
                processed = process_list(item)
                if processed:
                    result.append(processed)
            else:
                result.append(item)
        return result

    # For MOVE operation, find target node first
    if operation == Operation.MOVE:
        target_node = find_node_by_id(data['root_nodes'], target_property)
        if target_node:
            # Ensure target node has child_nodes array
            if 'child_nodes' not in target_node_ref['node']:
                target_node_ref['node']['child_nodes'] = []
            logging.debug(f"Target node ready for children: {target_node_ref['node']}")
        else:
            logging.error(f"Target node {target_property} not found")
            return data

    # Process the data
    if 'root_nodes' in data:
        # First pass: collect nodes to move and remove them from current locations
        data['root_nodes'] = process_list(data['root_nodes'])
        
        # Second pass: add collected nodes to target
        if operation == Operation.MOVE and target_node_ref['node'] and nodes_to_move:
            logging.debug(f"Moving {len(nodes_to_move)} nodes to target {target_property}")
            target_node_ref['node']['child_nodes'] = nodes_to_move
            logging.debug(f"Target node after move: {target_node_ref['node']}")
        
        return data
    else:
        return process_object(data)