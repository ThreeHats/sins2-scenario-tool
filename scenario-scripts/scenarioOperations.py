import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Union, Optional
from enum import Enum

class Operation(Enum):
    ADD = "add"
    CHANGE = "change"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    SCALE = "scale"
    REMOVE = "remove_node"
    MOVE = "set_parent_node"
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
    
    # Keep track of nodes to move
    nodes_to_move = []
    
    def find_and_update_target(nodes: List[Dict], target_id: str, new_children: List[Dict]) -> bool:
        """Find target node and update its children"""
        for node in nodes:
            if str(node.get('id')) == target_id:
                # Append new children instead of replacing
                if 'child_nodes' not in node:
                    node['child_nodes'] = []
                node['child_nodes'].extend(new_children)
                logging.debug(f"Updated target node {target_id}, now has {len(node['child_nodes'])} children")
                return True
            if 'child_nodes' in node:
                if find_and_update_target(node['child_nodes'], target_id, new_children):
                    return True
        return False

    def process_value(current_value: Any) -> Any:
        # Try to convert string numbers to float first
        if isinstance(current_value, str):
            try:
                current_value = float(current_value)
            except ValueError:
                # If it's not a numeric string, we can't perform math operations
                if operation in [Operation.ADD, Operation.MULTIPLY, Operation.DIVIDE, Operation.SCALE]:
                    logging.warning(f"Cannot perform {operation.value} on non-numeric value: {current_value}")
                    return current_value

        if operation == Operation.ADD:
            return current_value + (value * operator_adjustment)
        elif operation == Operation.MULTIPLY:
            return current_value * (value * operator_adjustment)
        elif operation == Operation.DIVIDE:
            if value * operator_adjustment == 0:
                logging.warning("Cannot divide by zero")
                return current_value
            return current_value / (value * operator_adjustment)
        elif operation == Operation.SCALE:
            return current_value * operator_adjustment
        elif operation == Operation.CHANGE:
            return value
        return current_value

    def process_object(obj: Dict) -> Optional[Dict]:
        if not isinstance(obj, dict):
            return obj
            
        # Process children first to ensure we handle nested structures
        if 'child_nodes' in obj:
            obj['child_nodes'] = process_list(obj['child_nodes'])
        
        # Check if this object matches our filter
        if filter_group.evaluate(obj):
            logging.debug(f"Found matching object: {obj}")
            if operation == Operation.REMOVE:
                logging.debug("Removing object")
                return None
            elif operation == Operation.MOVE:
                # Create a deep copy of the node including its children
                moved_node = obj.copy()
                if 'child_nodes' in obj:
                    moved_node['child_nodes'] = obj['child_nodes']
                nodes_to_move.append(moved_node)
                logging.debug(f"Marked node {obj.get('id')} for moving with {len(obj.get('child_nodes', []))} children")
                return None  # Remove from original location
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
        
        return obj

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

    # Process the data
    if 'root_nodes' in data:
        # First pass: collect and remove nodes to move
        data['root_nodes'] = process_list(data['root_nodes'])
        
        # Update target node with collected nodes
        if operation == Operation.MOVE and nodes_to_move:
            logging.debug(f"Moving {len(nodes_to_move)} nodes to target {target_property}")
            if not find_and_update_target(data['root_nodes'], str(target_property), nodes_to_move):
                logging.error(f"Failed to find target node {target_property} for updating")

        return data
    else:
        return process_object(data)