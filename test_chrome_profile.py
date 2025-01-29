from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import json
import time
import psutil

def kill_existing_chrome():
    """Kill any existing Chrome processes"""
    print("Closing any existing Chrome windows...")
    for proc in psutil.process_iter(['name']):
        try:
            # Check for both Chrome and Chromedriver processes
            if proc.info['name'] in ['Google Chrome', 'chromedriver']:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    time.sleep(2)  # Give Chrome time to fully close

def get_chrome_profiles():
    # Path to Chrome profiles on macOS
    chrome_path = f'/Users/{os.getenv("USER")}/Library/Application Support/Google/Chrome'
    local_state_path = os.path.join(chrome_path, 'Local State')
    
    try:
        with open(local_state_path, 'r') as f:
            data = json.load(f)
            # Get info about profiles
            profiles = data.get('profile', {}).get('info_cache', {})
            return profiles
    except Exception as e:
        print(f"Error reading Chrome profiles: {e}")
        return {}

def list_and_select_profile():
    profiles = get_chrome_profiles()
    
    if not profiles:
        print("No Chrome profiles found!")
        return None, None
    
    print("\nAvailable Chrome profiles:")
    print("-" * 50)
    
    # Create a list of profiles for easy selection
    profile_list = list(profiles.items())
    for idx, (profile_dir, profile_info) in enumerate(profile_list, 1):
        name = profile_info.get('name', 'Unnamed')
        print(f"{idx}. {name} (Directory: {profile_dir})")
    
    print("-" * 50)
    
    while True:
        try:
            choice = int(input("\nSelect a profile number (or 0 to exit): "))
            if choice == 0:
                return None, None
            if 1 <= choice <= len(profile_list):
                selected_profile = profile_list[choice-1]
                return selected_profile[0], selected_profile[1].get('name')
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

def test_chrome_profile():
    driver = None
    
    try:
        profile_dir, profile_name = list_and_select_profile()
        
        if not profile_dir:
            print("No profile selected. Exiting...")
            return
        
        print(f"\nLaunching Chrome with profile: {profile_name}")
        
        # Close any existing Chrome windows
        kill_existing_chrome()
        
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument(f'--user-data-dir=/Users/{os.getenv("USER")}/Library/Application Support/Google/Chrome')
        chrome_options.add_argument(f'--profile-directory={profile_dir}')
        
        # Make automation smoother
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Setup Chrome driver with options
        print("Initializing Chrome driver...")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Navigate to HubSpot
        print("Opening HubSpot...")
        driver.get("https://app.hubspot.com/")
        
        # Keep the browser open for verification
        print("Browser will stay open. Press Ctrl+C to exit...")
        while True:
            time.sleep(1)
        
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

if __name__ == "__main__":
    test_chrome_profile() 