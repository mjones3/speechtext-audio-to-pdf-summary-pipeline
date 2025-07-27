#!/bin/bash

# Meeting Pipeline Runner Script
# Creates virtual env, runs the pipeline, then cleans up

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
PYTHON_SCRIPT="$SCRIPT_DIR/meeting_pipeline.py"

print_status "🚀 Meeting Pipeline Runner"
echo "=" | head -c 50; echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python3 not found. Please install Python 3.7+ first."
    exit 1
fi

# Check if API key is set
if [ -z "$SPEECHTEXT_API_KEY" ]; then
    print_warning "SPEECHTEXT_API_KEY environment variable not set"
    echo "Please set your API key first:"
    echo "export SPEECHTEXT_API_KEY='your_api_key_here'"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Exiting. Please set API key first."
        exit 1
    fi
fi

# Check if required files exist
if [ ! -f "$PYTHON_SCRIPT" ]; then
    print_error "meeting_pipeline.py not found in script directory"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    print_status "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    if [ $? -eq 0 ]; then
        print_success "Virtual environment created"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
else
    print_status "📦 Virtual environment already exists"
fi

# Activate virtual environment
print_status "🔧 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

if [ $? -eq 0 ]; then
    print_success "Virtual environment activated"
else
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Upgrade pip
print_status "📦 Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1

# Install/update requirements
if [ -f "$REQUIREMENTS_FILE" ]; then
    print_status "📦 Installing/updating dependencies..."
    pip install -r "$REQUIREMENTS_FILE"
    
    if [ $? -eq 0 ]; then
        print_success "Dependencies installed"
    else
        print_error "Failed to install dependencies"
        deactivate
        exit 1
    fi
else
    print_warning "requirements.txt not found, installing core dependencies..."
    pip install requests reportlab pyperclip
fi

# Run the Python script
print_status "🎯 Running meeting pipeline..."
echo "=" | head -c 50; echo

# Pass all command line arguments to the Python script
python "$PYTHON_SCRIPT" "$@"
EXIT_CODE=$?

echo
echo "=" | head -c 50; echo

# Deactivate virtual environment
print_status "🔧 Deactivating virtual environment..."
deactivate

# Final status
if [ $EXIT_CODE -eq 0 ]; then
    print_success "✅ Pipeline completed successfully!"
else
    print_error "❌ Pipeline failed with exit code $EXIT_CODE"
fi

# Optional: Ask if user wants to view output directory
if [ $EXIT_CODE -eq 0 ]; then
    echo
    read -p "📁 Open output directory? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        OUTPUT_DIR="$SCRIPT_DIR/meeting_outputs"
        if [ -d "$OUTPUT_DIR" ]; then
            # Try to open directory based on OS
            if command -v open &> /dev/null; then
                # macOS
                open "$OUTPUT_DIR"
            elif command -v xdg-open &> /dev/null; then
                # Linux
                xdg-open "$OUTPUT_DIR"
            elif command -v explorer &> /dev/null; then
                # Windows (Git Bash)
                explorer "$OUTPUT_DIR"
            else
                print_status "Output directory: $OUTPUT_DIR"
            fi
        else
            print_warning "Output directory not found"
        fi
    fi
fi

exit $EXIT_CODE