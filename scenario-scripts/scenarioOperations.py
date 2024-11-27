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
            
        # Deep copy to avoid modifying original
        result = obj.copy()
        
        # Check if this object matches our filter
        if filter_group.evaluate(obj):
            logging.debug(f"Found matching object: {obj}")
            if operation == Operation.REMOVE:
                logging.debug("Removing object")
                return None
            elif target_property in obj:
                current_value = obj[target_property]
                if isinstance(current_value, (int, float)):
                    result[target_property] = process_value(current_value)
                    logging.debug(f"Modified {target_property} from {current_value} to {result[target_property]}")
        
        # Process nested dictionaries and lists
        for key, value in obj.items():
            if isinstance(value, dict):
                processed = process_object(value)
                if processed is not None:
                    result[key] = processed
            elif isinstance(value, list):
                result[key] = process_list(value)
        
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

    # Start processing from the root
    return process_object(data)