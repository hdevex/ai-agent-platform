"""
Install script for Excel processing tools
"""

import subprocess
import sys
import os

def install_package(package):
    """Install a package using pip."""
    try:
        print(f"📦 Installing {package}...")
        result = subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ {package} installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def check_installation():
    """Check if packages are installed and working."""
    packages = {
        'pandas': 'pd',
        'openpyxl': 'openpyxl'
    }
    
    print("\n🔍 Checking installations...")
    for package, import_name in packages.items():
        try:
            __import__(package)
            print(f"✅ {package} is available")
        except ImportError:
            print(f"❌ {package} not found")

def main():
    print("🛠️  Excel Analysis Tools Installer")
    print("=" * 40)
    
    # Install the best Excel tools
    packages_to_install = [
        "pandas",
        "openpyxl", 
        "xlrd"  # For older Excel files if needed
    ]
    
    for package in packages_to_install:
        install_package(package)
    
    # Check if everything is working
    check_installation()
    
    print("\n🎉 Installation complete!")
    print("💡 Now you can run: python real_excel_analyzer.py")
    print("📊 This will give Dato' Ahmad full access to your Excel file data")

if __name__ == "__main__":
    main()