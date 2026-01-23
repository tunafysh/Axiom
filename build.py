#!/usr/bin/env python3
"""
Build script for Axiom CPU project.
Handles building both the Rust assembler and C emulator.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
import platform
import shutil
import time
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"


def log_info(msg: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}[INFO]{Colors.END} {msg}")


def log_success(msg: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.END} {msg}")


def log_warning(msg: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARNING]{Colors.END} {msg}")


def log_error(msg: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[ERROR]{Colors.END} {msg}")


def run_command(cmd: list, cwd: str = None, description: str = "", check: bool = True) -> bool:
    """
    Run a shell command and return success status.
    
    Args:
        cmd: Command and arguments as list
        cwd: Working directory for command
        description: Description of what the command does
        check: If True, raise exception on non-zero exit code
        
    Returns:
        True if command succeeded, False otherwise
    """
    if description:
        log_info(description)
    
    try:
        result = subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {' '.join(cmd)}")
        if e.stderr:
            log_error(f"Error: {e.stderr}")
        return False
    except FileNotFoundError as e:
        log_error(f"Command not found: {cmd[0]}")
        return False


def check_raylib() -> bool:
    """
    Check if raylib is installed and available to CMake.
    
    Returns:
        True if raylib is found, False otherwise
    """
    log_info("Checking for raylib...")
    
    # Try to find raylib via pkg-config
    result = subprocess.run(
        ["pkg-config", "--exists", "raylib"],
        check=False,
        capture_output=True
    )
    
    if result.returncode == 0:
        log_success("raylib found")
        return True
    
    log_warning("raylib not found")
    return False


def install_raylib() -> bool:
    """
    Attempt to install raylib using the system package manager.
    
    Returns:
        True if installation succeeded, False otherwise
    """
    log_info("Attempting to install raylib...")
    
    system = platform.system()
    
    if system == "Linux":
        # Try apt first
        if shutil.which("apt"):
            log_info("Installing raylib via apt...")
            return run_command(
                ["sudo", "apt", "install", "-y", "libraylib-dev"],
                description="Running apt install"
            )
        # Try dnf
        elif shutil.which("dnf"):
            log_info("Installing raylib via dnf...")
            return run_command(
                ["sudo", "dnf", "install", "-y", "raylib-devel"],
                description="Running dnf install"
            )
        # Try pacman
        elif shutil.which("pacman"):
            log_info("Installing raylib via pacman...")
            return run_command(
                ["sudo", "pacman", "-S", "--noconfirm", "raylib"],
                description="Running pacman install"
            )
        else:
            log_error("No supported package manager found on Linux")
            return False
    
    elif system == "Darwin":  # macOS
        if shutil.which("brew"):
            log_info("Installing raylib via Homebrew...")
            return run_command(
                ["brew", "install", "raylib"],
                description="Running brew install"
            )
        else:
            log_error("Homebrew not found. Please install Homebrew first.")
            return False
    
    elif system == "Windows":
        log_error("Automatic raylib installation not supported on Windows")
        log_error("Please install raylib from https://github.com/raysan5/raylib/wiki/Working-on-Windows")
        return False
    
    else:
        log_error(f"Unsupported system: {system}")
        return False


def ensure_raylib(skip_install: bool = False) -> bool:
    """
    Ensure raylib is available, optionally attempting installation.
    
    Args:
        skip_install: If True, don't attempt installation
        
    Returns:
        True if raylib is available, False otherwise
    """
    if check_raylib():
        return True
    
    if skip_install:
        log_error("raylib is required but not installed. Use 'python build.py --install-deps' to install.")
        return False
    
    log_warning("raylib not found. Attempting to install...")
    if install_raylib():
        # Verify installation
        if check_raylib():
            log_success("raylib installed successfully")
            return True
        else:
            log_error("raylib installation verification failed")
            return False
    else:
        log_error("Failed to install raylib")
        return False


def get_source_files(root_dir: Path, component: str = "both") -> list:
    """
    Get all source files to watch for changes.
    
    Args:
        root_dir: Root directory of the project
        component: "assembler", "emulator", or "both"
        
    Returns:
        List of Path objects for source files
    """
    files = []
    
    if component in ["assembler", "both"]:
        assembler_src = root_dir / "Assembler" / "src"
        if assembler_src.exists():
            files.extend(assembler_src.rglob("*.rs"))
    
    if component in ["emulator", "both"]:
        emulator_src = root_dir / "Emulator" / "src"
        if emulator_src.exists():
            files.extend(emulator_src.rglob("*.c"))
            files.extend(emulator_src.rglob("*.h"))
        # Also watch CMakeLists.txt
        cmake_file = root_dir / "Emulator" / "CMakeLists.txt"
        if cmake_file.exists():
            files.append(cmake_file)
    
    return files


def watch_and_build(
    root_dir: Path,
    component: str = "both",
    release: bool = False,
    shared: bool = False,
    skip_raylib_check: bool = False,
    execute: bool = False
) -> None:
    """
    Watch source files for changes and automatically rebuild.
    
    Args:
        root_dir: Root directory of the project
        component: "assembler", "emulator", or "both"
        release: Build in release mode
        shared: Build emulator as shared library
        skip_raylib_check: Skip raylib checks
        execute: Execute emulator after successful build
    """
    log_info("Starting watch mode...")
    log_info("Watching for changes. Press Ctrl+C to exit.")
    
    source_files = get_source_files(root_dir, component)
    file_mtimes = {f: f.stat().st_mtime for f in source_files if f.exists()}
    
    emulator_binary = root_dir / "Emulator" / "build" / "axiom-emulator"
    emulator_process = None
    
    def start_emulator():
        """Start the emulator process."""
        nonlocal emulator_process
        if execute and emulator_binary.exists():
            try:
                if emulator_process and emulator_process.poll() is None:
                    log_info("Terminating previous emulator process...")
                    emulator_process.terminate()
                    try:
                        emulator_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        emulator_process.kill()
                
                log_info("Starting emulator...")
                emulator_process = subprocess.Popen(
                    [str(emulator_binary)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                log_success("Emulator started")
            except Exception as e:
                log_error(f"Failed to start emulator: {e}")
    
    def build_and_execute():
        """Perform build and optionally execute."""
        success = True
        
        if component in ["assembler", "both"]:
            if not build_assembler(root_dir, release=release):
                success = False
        
        if component in ["emulator", "both"]:
            if not build_emulator(root_dir, release=release, shared=shared, skip_raylib_check=skip_raylib_check):
                success = False
        
        if success:
            log_success(f"Build successful at {datetime.now().strftime('%H:%M:%S')}")
            start_emulator()
        else:
            log_error("Build failed")
        
        return success
    
    # Initial build
    build_and_execute()
    
    try:
        while True:
            time.sleep(1)
            
            # Refresh source files list in case new files were added
            source_files = get_source_files(root_dir, component)
            
            # Check for modified files
            changed = False
            for source_file in source_files:
                if not source_file.exists():
                    continue
                
                mtime = source_file.stat().st_mtime
                if source_file not in file_mtimes:
                    file_mtimes[source_file] = mtime
                    changed = True
                    log_info(f"New file detected: {source_file.relative_to(root_dir)}")
                elif file_mtimes[source_file] != mtime:
                    file_mtimes[source_file] = mtime
                    changed = True
                    log_info(f"File changed: {source_file.relative_to(root_dir)}")
            
            if changed:
                log_info("Rebuilding...")
                build_and_execute()
    
    except KeyboardInterrupt:
        log_info("\nWatch mode interrupted")
        if emulator_process and emulator_process.poll() is None:
            log_info("Terminating emulator...")
            emulator_process.terminate()
            try:
                emulator_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                emulator_process.kill()
        sys.exit(0)


def build_assembler(root_dir: Path, release: bool = False) -> bool:
    """
    Build the Rust assembler using Cargo.
    
    Args:
        root_dir: Root directory of the project
        release: If True, build in release mode
        
    Returns:
        True if build succeeded, False otherwise
    """
    log_info("Building Rust Assembler...")
    
    assembler_dir = root_dir / "Assembler"
    if not assembler_dir.exists():
        log_error("Assembler directory not found")
        return False
    
    cmd = ["cargo", "build"]
    if release:
        cmd.append("--release")
    
    if not run_command(cmd, cwd=str(assembler_dir), description="Compiling assembler..."):
        return False
    
    log_success("Assembler built successfully")
    return True


def build_emulator(root_dir: Path, release: bool = False, shared: bool = False, skip_raylib_check: bool = False) -> bool:
    """
    Build the C emulator using CMake.
    
    Args:
        root_dir: Root directory of the project
        release: If True, build in release mode
        shared: If True, build as shared library instead of executable
        skip_raylib_check: If True, skip raylib availability check
        
    Returns:
        True if build succeeded, False otherwise
    """
    log_info("Building C Emulator...")
    
    emulator_dir = root_dir / "Emulator"
    if not emulator_dir.exists():
        log_error("Emulator directory not found")
        return False
    
    # Check for raylib dependency
    if not skip_raylib_check:
        if not ensure_raylib():
            log_error("Cannot build emulator without raylib")
            return False
    
    # Create build directory
    build_dir = emulator_dir / "build"
    build_dir.mkdir(exist_ok=True)
    
    # Configure with CMake
    cmake_cmd = ["cmake", ".."]
    if release:
        cmake_cmd.extend(["-DCMAKE_BUILD_TYPE=Release"])
    else:
        cmake_cmd.extend(["-DCMAKE_BUILD_TYPE=Debug"])
    
    if shared:
        cmake_cmd.append("-DBUILD_AS_EXECUTABLE=OFF")
    else:
        cmake_cmd.append("-DBUILD_AS_EXECUTABLE=ON")
    
    if not run_command(cmake_cmd, cwd=str(build_dir), description="Configuring CMake..."):
        return False
    
    # Build with CMake
    if not run_command(["cmake", "--build", "."], cwd=str(build_dir), description="Compiling emulator..."):
        return False
    
    log_success("Emulator built successfully")
    return True


def clean(root_dir: Path) -> bool:
    """
    Clean build artifacts.
    
    Args:
        root_dir: Root directory of the project
        
    Returns:
        True if cleanup succeeded, False otherwise
    """
    log_info("Cleaning build artifacts...")
    
    assembler_dir = root_dir / "Assembler"
    emulator_dir = root_dir / "Emulator"
    
    # Clean Rust build
    if assembler_dir.exists():
        if not run_command(["cargo", "clean"], cwd=str(assembler_dir)):
            log_warning("Failed to clean Rust artifacts")
    
    # Clean CMake build
    build_dir = emulator_dir / "build"
    if build_dir.exists():
        try:
            shutil.rmtree(build_dir)
            log_info("Removed CMake build directory")
        except Exception as e:
            log_warning(f"Failed to remove build directory: {e}")
    
    log_success("Cleanup complete")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build script for Axiom CPU project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build.py                           # Build both assembler and emulator
  python build.py --release                 # Build in release mode
  python build.py --assembler               # Build only assembler
  python build.py --emulator                # Build only emulator
  python build.py --emulator --shared       # Build emulator as shared library
  python build.py --install-deps            # Install missing dependencies
  python build.py --skip-raylib-check       # Build without raylib checks
  python build.py --watch                   # Watch and rebuild on changes
  python build.py --watch --emulator        # Watch emulator only
  python build.py --run                     # Watch, rebuild, and auto-execute emulator
  python build.py --run --emulator          # Watch emulator and auto-run
  python build.py --clean                   # Clean all build artifacts
        """
    )
    
    parser.add_argument(
        "--assembler",
        action="store_true",
        help="Build only the assembler"
    )
    parser.add_argument(
        "--emulator",
        action="store_true",
        help="Build only the emulator"
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Build in release mode"
    )
    parser.add_argument(
        "--shared",
        action="store_true",
        help="Build emulator as shared library (requires --emulator)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts"
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install missing dependencies (raylib)"
    )
    parser.add_argument(
        "--skip-raylib-check",
        action="store_true",
        help="Skip raylib availability check (for systems with custom raylib setup)"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch source files for changes and rebuild automatically"
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Watch and automatically re-execute the emulator after rebuild"
    )
    
    args = parser.parse_args()
    
    # Get root directory
    root_dir = Path(__file__).parent
    
    # Handle clean operation
    if args.clean:
        return 0 if clean(root_dir) else 1
    
    # Handle install dependencies operation
    if args.install_deps:
        log_info("Installing dependencies...")
        if install_raylib():
            log_success("Dependencies installed successfully")
            return 0
        else:
            log_error("Failed to install dependencies")
            return 1
    
    # Handle watch/run modes
    if args.watch or args.run:
        # Determine what to watch
        watch_component = "both"
        if args.assembler and not args.emulator:
            watch_component = "assembler"
        elif args.emulator and not args.assembler:
            watch_component = "emulator"
        
        watch_and_build(
            root_dir,
            component=watch_component,
            release=args.release,
            shared=args.shared,
            skip_raylib_check=args.skip_raylib_check,
            execute=args.run
        )
        return 0
    
    # Determine what to build
    build_assembler_flag = args.assembler or (not args.assembler and not args.emulator)
    build_emulator_flag = args.emulator or (not args.assembler and not args.emulator)
    
    success = True
    
    # Build assembler if requested
    if build_assembler_flag:
        if not build_assembler(root_dir, release=args.release):
            success = False
    
    # Build emulator if requested
    if build_emulator_flag:
        if not build_emulator(root_dir, release=args.release, shared=args.shared, skip_raylib_check=args.skip_raylib_check):
            success = False
    
    if success:
        log_success("Build complete!")
        return 0
    else:
        log_error("Build failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
