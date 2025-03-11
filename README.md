### WIP

- See [project board](https://github.com/users/ThreeHats/projects/5) for progress

# Sins 2 Scenario Tool

A tool for managing and modifying Sins of a Solar Empire 2 scenarios.

![screenshot](https://github.com/ThreeHats/sins2-community-tools/blob/main/images/image.png?raw=true)

## Features

### Scenario Management
   - Load scenarios via drag & drop
   - Save scenarios to custom locations
   - Direct integration with Steam and Epic game directories
   - Support for both chart and generator scenario types
   - Auto-detection of scenario type

### Visual Galaxy Editor
   - Interactive galaxy map visualization
   - Node selection and multi-selection
   - Direct property editing
   - Visual node position adjustment
   - Display options for:
      - Grid
      - Orbits
      - Star lanes
      - Wormholes
      - Regular lanes

### Node Operations
   - Add new properties to nodes
   - Change existing property values
   - Move nodes to new parents
   - Remove nodes
   - Batch operations on multiple nodes
   - Filter nodes by properties:
      - Multiple filter conditions
      - Numeric comparisons
      - String matching

### Template System
   - Save scenarios as reusable templates
   - Organize templates by type (chart/generator)
   - User and community template sections
   - Quick loading of common scenario setups

### Script System
   - Apply Python scripts to modify scenarios
   - Separate script sections for chart and generator scenarios
   - User and community script directories
   - Real-time script directory monitoring
   - Community scripts for common operations:
      - System flattening (moving all systems to the root node)
      - Wormhole pairing
      - Node removal

## Installation

1. Download scenario-tool.exe from [GitHub Releases](https://github.com/ThreeHats/sins2-community-tools/releases/latest)
2. Place the downloaded .exe file in your desired location
3. Run the scenario-tool.exe file

## Usage

### Basic Operations

1. **Loading and Saving Scenarios**
   - Drag and drop a .scenario file onto the tool or load from templates list

2. **Editing Nodes**
   - Click nodes to select them
   - Shift+click or click+drag to multi-select
   - Edit properties in the Node Details panel
   - Drag nodes to move them

3. **Batch Operations**
   - Use filters to select nodes
   - Apply operations to all selected nodes
   - Available operations:
     - Add properties
     - Change values
     - Move nodes
     - Remove nodes

4. **Saving Work**
   - Save directly to game directories
   - Place scenarios in the user templates directory for easy access
   - All changes are automatically saved in the working directory

5. **Updating Community Content and Applying Scripts**
   - Use the "Get Community Content" button to update the community templates and scripts
   - When an update is available, a notification will appear at launch

### Working with Scripts

Scripts must follow these requirements:

1. Include a `transform_scenario(working_dir)` function
2. Handle logging appropriately
3. Place in the correct directory:
   - Chart scripts: `scripts/chart/`
   - Generator scripts: `scripts/generator/`


## Development

### Adding New Scripts

1. Create a new .py file in the appropriate scripts directory (use an existing file as a template)
2. Implement the required `transform_scenario(working_dir)` function
3. Use logging for operation feedback
4. Handle errors appropriately

### File Requirements

- Chart scenarios require:
  - galaxy_chart.json
  - galaxy_chart_fillings.json
  - scenario_info.json

- Generator scenarios require:
  - galaxy_chart_generator_params.json
  - galaxy_chart_fillings.json
  - scenario_info.json

## Contributing

1. Fork the repository
2. Add your scripts to the community directory
3. Add a test scenario to the templates directory with the same name as your script (e.g. `remove_all_but_one_system_and_range.py` -> `remove_all_but_one_system_and_range.scenario`)
4. Submit a pull request

## License

MIT License - See LICENSE file for details
