# Open Civil

Open Civil is a free, educational structural analysis software designed to bridge the gap between simplified 2D textbook problems and complex commercial "black box" software. 

It provides a **fully transparent workspace** where students can model 3D structures, visualize internal forces, and inspect the underlying mathematical matrices (Stiffness, Transformation, etc.) in real-time.

## Screenshots

| 3D Modeling | Analysis Results |
|:---:|:---:|
| <img src="images/hero-main.png" width="400"> | <img src="images/feature-3.png" width="400"> |
| *Real-time 3D Extrusions* | *Nodal deformations & Fixed end forces* |

## Key Features

* **Educational "Glass Box" Engine**:
    * View the raw **12x12 Stiffness Matrix [k]** for any element.
    * Inspect **Transformation Matrices [T]** and Fixed End Force vectors.
    * Trace the solver's logic step-by-step.

* **Advanced Structural Modeling**:
    * Full **3D Timoshenko Beam Theory** (Shear Deformation).
    * **Rigid End Offsets** & Cardinal Insertion Points.
    * **Member Releases** (Moment/Shear) using static condensation.

* **Interactive Visualization**:
    * Fast OpenGL rendering (Arcball rotation, Pan, Zoom).
    * True-to-scale extruded shapes (I-Beams, T-Beams, Rectangular).
    * Visual "Matrix Spy" tool for debugging models.

* **Transparent Data**:
    * Saves projects as human-readable **JSON (.mf)** files.
    * Easy to parse with Python, MATLAB, or Excel for research.

## Tech Stack (Software Core)

* **Language**: Python 3.10+
* **GUI Framework**: PyQt6
* **Graphics**: PyOpenGL / PyQtGraph
* **Math Kernel**: NumPy & SciPy (Sparse Linear Algebra)

## Installation & Setup

### 📥 Download Installer (Windows)

The source code is currently private while in development. This repository hosts the official website.

**[Download the latest .exe here](https://github.com/OpenCivil-Project/OpenCivil/releases/latest)**

## Usage Guide

1. **Define Grid**: Start a new model and define your X/Y/Z grid lines.
2. **Materials & Sections**: Go to Define > Section Properties to create I-beams or Concrete Rectangles.
3. **Draw**: Use the Draw Frame tool to click-and-drag beams between grid points.
4. **Assign**: Select members to assign Loads, Releases, or Supports.
5. **Analyze**: Press F5 or go to Analyze > Run Analysis.
6. **Inspect**: Right-click any element to see its "Matrix Spy" or Free Body Diagram.

## 🤝 Feedback & Support

This is a student project created for educational purposes. 

If you find a bug or have a suggestion, please **[Open an Issue](https://github.com/OpenCivil-Project/OpenCivil/issues)** in this repository.

## Author

**Shaikh Ahmed Azad** Civil Engineering Student | METU  
[GitHub Profile](https://github.com/ShaikhAhmedAzad)
