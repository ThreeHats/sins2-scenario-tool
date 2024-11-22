### WIP

# Sins 2 Scenario Tool

A tool for managing and modifying Sins of a Solar Empire 2 scenarios.

![screenshot](https://github.com/JustAnotherIdea/sins2-community-tools/blob/main/images/image.png?raw=true)

## Features

- **Scenario Management**
  - Load and extract .scenario files
  - Save scenarios to custom locations
  - Direct integration with Steam and Epic game directories
  - Support for both chart and generator scenario types

- **Template System**
  - Save scenarios as reusable templates
  - Organize templates by type (chart/generator)
  - User and community template sections

- **Script System**
  - Apply Python scripts to modify scenarios
  - Separate script sections for chart and generator scenarios
  - User and community script directories
  - Real-time script directory monitoring

## Installation

1. Ensure Python 3.8+ is installed
2. Open a terminal in the scenario-scripts directory
3. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the script:
   ```
   python scenarioTool.py
   ```


## Usage

### Basic Operations

1. **Loading Scenarios**
   - Drag and drop a .scenario file onto the tool
   - The tool automatically detects scenario type (chart/generator)

2. **Saving Scenarios**
   - Enter a name for your scenario
   - Choose a save location (default, Steam, or Epic directory)
   - Click "Save Scenario"

3. **Templates**
   - Save frequently used scenarios as templates
   - Templates are organized by type and source (user/community)

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
