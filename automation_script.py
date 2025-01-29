from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import json
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

def get_user_input():
    while True:
        try:
            total = int(input("How many pairs would you like to process? "))
            if total <= 0:
                print("Please enter a positive number")
                continue
            return total
        except ValueError:
            print("Please enter a valid number")

def login_to_hubspot(driver):
    print("Handling login...")
    
    # Wait for email input field
    email_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
    )
    
    # Get credentials from environment variables or prompt user
    email = os.getenv('HUBSPOT_EMAIL') or input("Enter your HubSpot email: ")
    password = os.getenv('HUBSPOT_PASSWORD') or input("Enter your HubSpot password: ")
    
    # Enter email and click Next
    email_input.send_keys(email)
    next_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    next_button.click()
    
    # Wait for password field
    time.sleep(2)
    password_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
    )
    
    # Enter password and submit
    password_input.send_keys(password)
    login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    login_button.click()
    
    # Wait for login to complete
    time.sleep(5)
    print("Login completed")

def process_duplicates(driver, pairs_to_process):
    try:
        # Find all Review buttons using the exact attributes from your HTML
        review_buttons = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((
                By.CSS_SELECTOR, 
                "button[aria-label='Review'][data-test-id='reviewDuplicates']"
            ))
        )
        
        total_pairs = len(review_buttons)
        print(f"Found {total_pairs} total pairs")
        
        if pairs_to_process > total_pairs:
            print(f"Warning: Only {total_pairs} pairs available. Will process all available pairs.")
            pairs_to_process = total_pairs
        
        print(f"Will process {pairs_to_process} pairs")
        proceed = input("Press Enter to continue or type 'n' to cancel: ")
        if proceed.lower() == 'n':
            return False
            
        # Process requested number of pairs
        for i in range(pairs_to_process):
            try:
                print(f"\nProcessing pair {i + 1} of {pairs_to_process}...")
                
                # Click the Review button
                review_buttons[i].click()
                time.sleep(2)
                
                # Wait for the modal to appear
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.modal-dialog"))
                )
                
                # Find both contact number elements
                contact_numbers = driver.find_elements(
                    By.CSS_SELECTOR,
                    "dl dd:nth-child(6) span span span span"
                )
                
                if len(contact_numbers) < 2:
                    raise Exception("Could not find contact numbers")
                
                # Extract and compare the numbers
                num1 = int(contact_numbers[0].text)
                num2 = int(contact_numbers[1].text)
                
                print(f"Found contact numbers: {num1} and {num2}")
                
                # Find the record cards
                cards = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR,
                        "div.modal-dialog div[role='radiogroup'] > div"
                    ))
                )
                
                if len(cards) < 2:
                    raise Exception("Could not find record cards")
                
                # Click the appropriate card based on contact numbers
                if num2 > num1:
                    driver.execute_script("arguments[0].click();", cards[1])
                    print("Selected second record (more contacts)")
                else:
                    driver.execute_script("arguments[0].click();", cards[0])
                    print("Selected first record (more or equal contacts)")
                
                time.sleep(1)  # Give the UI a moment to update after selection
                
                # Find and click the Merge button - trying multiple selectors
                try:
                    # First try the footer button
                    merge_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((
                            By.CSS_SELECTOR,
                            "div.modal-dialog footer button.private-button--primary"
                        ))
                    )
                except:
                    try:
                        # Try finding by button text
                        merge_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((
                                By.XPATH,
                                "//button[contains(text(), 'Merge')]"
                            ))
                        )
                    except:
                        # Last resort - try finding any primary button in the modal
                        merge_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((
                                By.CSS_SELECTOR,
                                "div.modal-dialog button[type='button']:not([class*='cancel'])"
                            ))
                        )
                
                print("Clicking Merge button...")
                try:
                    merge_button.click()
                except:
                    # If regular click fails, try JavaScript click
                    driver.execute_script("arguments[0].click();", merge_button)
                
                # Wait for the merge to complete and modal to close
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.modal-dialog"))
                )
                
                print(f"Pair {i + 1} merged successfully")
                
                # Wait and refresh for next pair
                time.sleep(2)
                driver.refresh()
                time.sleep(3)
                
                # Re-find the review buttons after refresh
                review_buttons = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR, 
                        "button[aria-label='Review'][data-test-id='reviewDuplicates']"
                    ))
                )
                
            except Exception as e:
                print(f"An error occurred with pair {i + 1}: {str(e)}")
                print("Continuing with next pair...")
                driver.refresh()
                time.sleep(3)
                
                # Re-find the review buttons after error
                review_buttons = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR, 
                        "button[aria-label='Review'][data-test-id='reviewDuplicates']"
                    ))
                )
                continue
        
        print("\nBatch completed successfully!")
        return True
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def automate_merge():
    print("Starting automation - Chrome browser will open shortly...")
    
    # Get Chrome profile
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
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Setup Chrome driver with options
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.maximize_window()
    
    try:
        # Initial page load
        print("\nOpening HubSpot duplicates page...")
        driver.get("https://app.hubspot.com/duplicates/22104039/companies?currentPage=1")
        
        print("\nWaiting for you to log in manually and navigate to the duplicates page...")
        print("Please log in through the browser if needed.")
        
        # Wait for initial login/navigation
        while True:
            current_url = driver.current_url
            if "duplicates" in current_url and not "login" in current_url:
                break
            time.sleep(2)
        
        print("\nDetected that you're on the duplicates page!")
        
        # Main processing loop
        while True:
            pairs_to_process = get_user_input()
            process_duplicates(driver, pairs_to_process)
            
            # Ask if user wants to process more
            more = input("\nWould you like to process more duplicates? (y/n): ")
            if more.lower() != 'y':
                break
            
            # Refresh page before next batch
            print("\nRefreshing page for next batch...")
            driver.refresh()
            time.sleep(3)
        
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if 'driver' in locals():
            choice = input("\nWould you like to keep the browser open? (y/n): ")
            if choice.lower() != 'y':
                driver.quit()
                print("Browser closed.")
            else:
                print("Browser will remain open. You can continue using it manually.")

if __name__ == "__main__":
    automate_merge() 