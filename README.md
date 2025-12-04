![ArUco Grid](static/match.png)

# ArUco Grid Generator

A responsive web application for generating printable ArUco marker grids used in pose estimation tasks for computer vision and robotics applications.

## Features

- **Customizable Grid Parameters**: Configure paper size (A4/A3), orientation (portrait/landscape), ArUco dictionary (4x4, 5x5, 6x6, 7x7, Original), number of rows and columns, marker size in mm, and separation between markers.
- **Real-Time Preview**: See a live preview of the generated grid as you adjust parameters.
- **Optional Overlays**: Toggle display of marker IDs, a scale ruler, generation parameters, and a coordinate system visualization.
- **Coordinate System Support**: Define a robotics-oriented coordinate system with customizable translations (X, Y, Z in mm) and rotations (Roll, Pitch, Yaw in degrees). The app calculates and provides transformation matrices for pose estimation.
- **High-Resolution PDF Export**: Generate print-ready PDFs with automatic scaling to fit the selected paper size.
- **Responsive Design**: Works seamlessly on desktop and mobile devices with a mobile-first approach.

## Technology Stack

- **Backend**: Python with Flask framework, OpenCV for ArUco marker generation, NumPy for mathematical operations, ReportLab for PDF creation, PIL for image processing.
- **Frontend**: HTML5, CSS3 (Tailwind CSS), vanilla JavaScript for responsive UI and API communication.
## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Local Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/arucogridgen.git
   cd arucogridgen
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the Flask application:
   ```bash
   python app.py
   ```
   Alternatively, use Flask's development server:
   ```bash
   export FLASK_APP=app.py
   export FLASK_ENV=development
   flask run
   ```

4. Open your web browser and navigate to `http://localhost:5000` to access the application.

### Docker Installation

1. Ensure Docker and Docker Compose are installed on your system.

2. Clone the repository and navigate to the project directory.

3. Build and run the application using Docker Compose:
   ```bash
   docker-compose up --build
   ```

4. Access the application at `http://localhost:5000` in your web browser.

---

This project is developed for academic and research purposes at the match, Leibniz University Hannover.

## Usage

Once the application is running, open your web browser and navigate to `http://localhost:5000`.

### Configuring the Grid

- **Paper Size and Orientation**: Select A4 or A3 paper size and choose portrait or landscape orientation.
- **ArUco Dictionary**: Choose from available dictionaries (e.g., 4x4, 5x5, 6x6, 7x7, Original) for marker generation.
- **Grid Dimensions**: Specify the number of rows and columns for the marker grid.
- **Marker Size and Separation**: Set the size of each marker in millimeters and the separation between markers.

### Overlays and Options

- **Show IDs**: Toggle to display marker IDs below each marker on the grid.
- **Show Scale**: Enable a 10 cm scale ruler on the output for reference.
- **Show Parameters**: Include grid generation parameters (paper size, dictionary, dimensions, etc.) on the PDF.
- **Show Coordinate System**: Visualize a robotics-oriented coordinate system overlay on the grid.

### Coordinate System Configuration

- Define base translation (X, Y, Z in mm) and rotation (Roll, Pitch, Yaw in degrees) for the coordinate system.
- The application automatically calculates transformation matrices, translations in meters, and quaternions for pose estimation tasks.

### Preview and Export

- Click the **Preview** button to generate and view a low-resolution preview of the grid with your current settings.
- Use the **Generate PDF** button to create and download a high-resolution, print-ready PDF that fits the selected paper size.
- The PDF includes all enabled overlays and can be directly printed for use in computer vision and robotics applications.

## References

```bibtex
@article{GARRIDOJURADO20142280,
title = {Automatic generation and detection of highly reliable fiducial markers under occlusion},
journal = {Pattern Recognition},
volume = {47},
number = {6},
pages = {2280-2292},
year = {2014},
issn = {0031-3203},
doi = {https://doi.org/10.1016/j.patcog.2014.01.005},
url = {https://www.sciencedirect.com/science/article/pii/S0031320314000235},
author = {S. Garrido-Jurado and R. Muñoz-Salinas and F.J. Madrid-Cuevas and M.J. Marín-Jiménez},
keywords = {Augmented reality, Fiducial marker, Computer vision},
abstract = {This paper presents a fiducial marker system specially appropriated for camera pose estimation in applications such as augmented reality and robot localization. Three main contributions are presented. First, we propose an algorithm for generating configurable marker dictionaries (in size and number of bits) following a criterion to maximize the inter-marker distance and the number of bit transitions. In the process, we derive the maximum theoretical inter-marker distance that dictionaries of square binary markers can have. Second, a method for automatically detecting the markers and correcting possible errors is proposed. Third, a solution to the occlusion problem in augmented reality applications is shown. To that aim, multiple markers are combined with an occlusion mask calculated by color segmentation. The experiments conducted show that our proposal obtains dictionaries with higher inter-marker distances and lower false negative rates than state-of-the-art systems, and provides an effective solution to the occlusion problem.}
}
```
