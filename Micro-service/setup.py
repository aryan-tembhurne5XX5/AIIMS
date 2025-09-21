# setup.py
import subprocess
import sys
import os

def install_packages():
    """Install required packages"""
    packages = [
        'selenium==4.15.0',
        'pandas==2.1.3',
        'openpyxl==3.1.2',
        'requests==2.31.0',
        'beautifulsoup4==4.12.2'
    ]
    
    for package in packages:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✅ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package}")

def setup_chromedriver():
    """Setup ChromeDriver"""
    print("🔧 Setting up ChromeDriver...")
    
    # Check if chromedriver exists
    try:
        result = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
        print(f"✅ ChromeDriver found: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ ChromeDriver not found. Please install:")
        print("   brew install chromedriver")
        return False

def main():
    print("🚀 Setting up NAMASTE extraction environment...")
    
    # Install Python packages
    install_packages()
    
    # Setup ChromeDriver
    setup_chromedriver()
    
    print("\n✅ Setup complete! You can now run the extraction script.")

if __name__ == "__main__":
    main()
