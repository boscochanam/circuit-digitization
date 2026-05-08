# SINA - Schematic Image to Netlist Tool

Welcome to **SINA**! This project is a computer vision-based system that automatically converts circuit schematic images into netlists for both **Integrated Circuits (IC)** and **Printed Circuit Boards (PCB)**. The system uses YOLOv8 object detection, OpenCV image processing, and OCR to detect circuit components, analyze wire connections, handle wire crossings, and generate structured netlists.

---

## Project Overview

SINA consists of two main modules:

### IC Netlist Generator

Converts integrated circuit schematic images into netlists by detecting circuit components, analyzing wire connections, and handling crossing points.

[View IC Documentation](Netlist%20Generator/IC/README.md)

### PCB Netlist Generator

Processes printed circuit board schematics with advanced text removal, pin detection, and multi-stage netlist generation with SPICE output support.

[View PCB Documentation](Netlist%20Generator/PCB/README.md)

---

## Repository Structure

```
SINA/
├── Netlist Generator/
│   ├── IC/                     # IC netlist generator module
│   │   ├── model_training/     # YOLO training resources
│   │   ├── program_test/       # Testing and validation tools
│   │   └── current_trained_model/
│   │
│   └── PCB/                    # PCB netlist generator module
│       ├── Model training/     # Training scripts and tools
│       ├── Program test/       # Testing utilities
│       ├── Current trained model/
│       ├── all models/Final/   # Production-ready scripts
│       └── other/              # Additional utilities
│
├── Database/                   # Project database files
└── README.md                   # This file
```

## Getting Started

### For IC Netlist Generation

1. Navigate to the IC module:

    ```bash
    cd "Netlist Generator/IC"
    ```

2. Follow the [IC README](Netlist%20Generator/IC/README.md) for detailed instructions.

3. Run your first netlist generation:
    ```bash
    cd program_test/netlist_generator_algorithm_test
    py netlist_generator.py
    ```

### For PCB Netlist Generation

1. Navigate to the PCB module:

    ```bash
    cd "Netlist Generator/PCB"
    ```

2. Follow the [PCB README](Netlist%20Generator/PCB/README.md) for detailed instructions.

3. Set up Google Cloud Vision credentials (see PCB README).

4. Run the complete pipeline:
    ```bash
    cd "all models/Final"
    python index.py --input data/input --output data/output
    ```

---

## Key Features

-   **Automated Component Detection** - YOLOv8-based object detection
-   **Text Removal** - OCR-based text filtering for cleaner analysis
-   **Pin Detection** - Edge scanning and keypoint detection
-   **Wire Tracing** - Skeletonization and crossing detection
-   **Netlist Generation** - JSON and SPICE format output
-   **Model Training** - Custom YOLO training pipeline with CVAT support

---

## Documentation

-   [IC Netlist Generator Documentation](Netlist%20Generator/IC/README.md)
-   [PCB Netlist Generator Documentation](Netlist%20Generator/PCB/README.md)

---

## How to Run Scripts

All scripts in this project are Python-based:

**Windows:**

```bash
py script_name.py
# or
python script_name.py
```

**macOS/Linux:**

```bash
python3 script_name.py
```

---

## Environment Variables

For certain features (like OpenAI API integration in IC module), create a `.env` file:

```env
OPENAI_API_KEY=your_api_key_here
```

---

## License

See [LICENSE.txt](LICENSE.txt) for details.

---
