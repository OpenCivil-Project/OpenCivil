# Open Civil

Open Civil is an open-source, educational structural analysis software designed to bridge the gap between simplified 2D textbook problems and complex commercial "black box" software. 

It provides a **fully transparent workspace** where students can model 3D structures, visualize internal forces, and inspect the underlying mathematical matrices (Stiffness, Transformation, etc.) in real-time.

## 📸 Screenshots

| 3D Modeling | Analysis Results |
|:---:|:---:|
| <img src="images/hero-main.png" width="400"> | <img src="images/feature-3.png" width="400"> |
| *Real-time 3D Extrusions* | *Deformed Shape & Diagrams* |

## ✨ Key Features

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

## 🛠️ Tech Stack

* **Language**: Python 3.10+
* **GUI Framework**: PyQt6
* **Graphics**: PyOpenGL / PyQtGraph
* **Math Kernel**: NumPy & SciPy (Sparse Linear Algebra)

## 🚀 Installation & Setup

### Option 1: Download Installer (Windows)

Download the latest `.exe` from the [Releases Page](https://github.com/ShaikhAhmedAzad/OpenCivil/releases/latest).

### Option 2: Run from Source (Developers)

**1. Clone the Repository**

```bash
git clone https://github.com/ShaikhAhmedAzad/OpenCivil.git
cd OpenCivil
```

**2. Create a Virtual Environment (Recommended)**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

**3. Install Dependencies**

```bash
pip install -r requirements.txt
```

**4. Run the App**

```bash
python main.py
```

## 📖 Usage Guide

1. **Define Grid**: Start a new model and define your X/Y/Z grid lines.
2. **Materials & Sections**: Go to Define > Section Properties to create I-beams or Concrete Rectangles.
3. **Draw**: Use the Draw Frame tool to click-and-drag beams between grid points.
4. **Assign**: Select members to assign Loads, Releases, or Supports.
5. **Analyze**: Press F5 or go to Analyze > Run Analysis.
6. **Inspect**: Right-click any element to see its "Matrix Spy" or Free Body Diagram.

## 🤝 Contributing

This is a student project created for educational purposes. Contributions, bug reports, and pull requests are welcome!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is open source and available for educational use.

## 👨‍💻 Author

**Shaikh Ahmed Azad**  
Civil Engineering Student | METU  
[GitHub Profile](https://github.com/ShaikhAhmedAzad)

---

### 🎯 Next Steps

Ready to get started? Check out the [Installation Guide](#-installation--setup) above or visit the [Wiki](https://github.com/ShaikhAhmedAzad/OpenCivil/wiki) for detailed tutorials.
