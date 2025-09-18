# The Gaffer's Clipboard

A Python application that uses OpenCV to extract and analyze in-depth stats from FIFA (EA FC) Career Mode post-match screens.

**Current Status:** In Development (Phase 2: Application Skeleton)

---

## Installation

This project requires a custom build of OpenCV and several Python packages.

### 1. Prerequisites

- Python 3.9+
- CMake
- A C++ Compiler (e.g., Visual Studio)
- Git

### 2. Build OpenCV from Source

This project requires a specific build of OpenCV. Please follow the official compilation guide, ensuring the following CMake flags are enabled:

- `WITH_FREETYPE`
- `WITH_QT`
- `WITH_CUDA` (Optional, for GPU acceleration)

### 3. Set Up the Environment

Clone the repository and set up the virtual environment.

```bash
# Clone the repository
git clone [https://github.com/your-username/Gaffers-Clipboard.git](https://github.com/your-username/Gaffers-Clipboard.git)
cd Gaffers-Clipboard

# Create and activate the virtual environment
python -m venv venv --system-site-packages
.\venv\Scripts\activate

# Install the required Python packages
pip install -r requirements.txt
