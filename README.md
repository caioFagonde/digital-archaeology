# Digital Archaeology & TUI Entropy Forensics

A high-performance, terminal-based "data archaeologist" tool. It functions as an advanced hex editor and analyzer that allows users to explore unknown or corrupted binary files in real-time. 

It visualizes byte distributions, Shannon entropy heatmaps, and pattern matches (e.g., file signatures, cryptographic constants) as the user scrolls through massive data payloads.

## System Architecture

The system is designed to handle files up to 10GB+ without loading them into RAM, maintaining a strictly non-blocking UI.

1. **Rust Backend Engine (`archaeology_engine`)**:
   - **Memory Mapping (`mmap2`)**: Bypasses RAM limitations by mapping the target file directly to virtual memory.
   - **Math Processor**: Computes Shannon Entropy ($H = -\sum p \log_2 p$) and byte frequency histograms on demand.
   - **Rules Engine**: Utilizes the Aho-Corasick algorithm for $O(n)$ multi-pattern byte matching to instantly detect embedded file headers or encryption signatures.
   - **Bridge**: Compiled natively as a Python module via `PyO3` and `Maturin`.

2. **Python Frontend (`tui_app`)**:
   - **Textual**: Drives the asynchronous Terminal User Interface (TUI).
   - **Virtual Scrolling**: The UI only requests the exact byte chunks required to fill the current terminal viewport, ensuring $O(1)$ memory usage regardless of file size.
   - **Rich Analytics**: Renders live progress bars, sparklines, and data tables.

## Prerequisites

- **Docker** and **Docker Compose**
- A terminal emulator that supports modern ANSI colors and UTF-8 rendering.

## Quick Start

The application runs entirely inside a Docker container. All dependencies, including the Rust toolchain and Python virtual environments, are handled automatically.

1. **Start the Application:**
   ```bash
   ./run.sh
Note: The first run will take a few minutes as it compiles the Rust engine in release mode. Subsequent runs will use Docker's cache.

Stop the Application:

code
Bash
./stop.sh
Usage & Keybindings
On initial startup, the system will auto-generate a 1MB test_sample.bin file containing distinct entropy regions and an injected ZIP header to demonstrate capabilities.

Key	Action
Up / k	Scroll up one line (16 bytes)
Down / j	Scroll down one line (16 bytes)
PageUp	Scroll up one full viewport
PageDown	Scroll down one full viewport
q	Quit application
Customizing Signatures
The Rules Engine scans for known byte signatures. You can add your own custom signatures by editing the rules/default_rules.json file on your host machine.

The format is a simple JSON array of objects containing a name and a hex string:

code
JSON
[
    {
        "name": "ZIP Archive (PKZIP)",
        "hex": "50 4B 03 04"
    },
    {
        "name": "PDF Document",
        "hex": "25 50 44 46 2D"
    },
    {
        "name": "JPEG Image",
        "hex": "FF D8 FF E0"
    }
]
Changes to the rules file will take effect the next time you launch the application via ./run.sh.

Analyzing Custom Files
To analyze your own files:

Place your target binary (e.g., target.bin, disk.img) into the data/ directory.

Update the test_file_path variable in frontend/src/main.py to point to /app/data/your_file_name.

Restart the application.