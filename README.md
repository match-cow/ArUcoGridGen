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
___

This project is developed for academic and research purposes at the match, Leibniz University Hannover.

## References

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
