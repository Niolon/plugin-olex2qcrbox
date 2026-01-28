# Olex2 QCrBox Plugin

A plugin for Olex2 that provides integration with the QCrBox API for running crystallographic calculations in the cloud.

## Features

- Browse and select QCrBox applications and commands
- Interactive and non-interactive calculation workflows
- Automatic CIF file upload and parameter management
- File parameter support with browse dialogs
- Manual status checking for running calculations
- Automatic TSCB file generation from results (when applicable)
- Result retrieval and automatic opening in Olex2

## Installation

### Prerequisites

- Olex2-next (with new python) installed on your system
- Local installation of QCrBox running and accessible
- Python 3.x (bundled with Olex2)

### Step 1: Build and Install QCrBoxAPIClient

The plugin requires the QCrBoxAPIClient library. You need to build a wheel file and install it.

**Build the wheel:**

1. Clone the QCrBoxAPIClient repository:
   ```bash
   git clone https://github.com/QCrBox/QCrBoxAPIClient.git
   cd QCrBoxAPIClient
   ```

2. Build the wheel using Poetry:
   ```bash
   pip install poetry
   poetry build
   ```
   
   This will create a `.whl` file in the `dist/` directory.

**Install in Olex2:**

In Olex2, run:
```
olex.m("pip install /path/to/QCrBoxAPIClient/dist/qcrboxapiclient-X.Y.Z-py3-none-any.whl")
```

Replace `/path/to/` with the actual path and `X.Y.Z` with the version number.

### Step 2: Install the Plugin

1. **Copy plugin files** to your Olex2 plugin directory:
   ```
   <olex2-directory>/util/pyUtil/PluginLib/plugin-olex2qcrbox/
   ```

2. **Enable the plugin** by editing (or creating) the `plugins.xld` file in your Olex2 base directory:
   ```
   <olex2-directory>/plugins.xld
   ```
   
   Add the following content:
   ```
   <Plugin
   <olex2qcrbox>
   >
   ```

3. **Restart Olex2** to load the plugin.
