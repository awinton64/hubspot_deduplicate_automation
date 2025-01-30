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
from selenium.common.exceptions import TimeoutException

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

def setup_browser():
    # Get Chrome profile
    profile_dir, profile_name = list_and_select_profile()
    if not profile_dir:
        print("No profile selected. Exiting...")
        return None
    
    print(f"\nLaunching Chrome with profile: {profile_name}")
    
    # Close any existing Chrome windows
    kill_existing_chrome()
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument(f'--user-data-dir=/Users/{os.getenv("USER")}/Library/Application Support/Google/Chrome')
    chrome_options.add_argument(f'--profile-directory={profile_dir}')
    
    # Add options to make automation smoother and more stealthy
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Additional stealth options
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    
    # Setup Chrome driver with options
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    # Additional stealth settings after driver creation
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    driver.maximize_window()
    return driver

def get_domain_rank(domain):
    """Rank domain extensions by commonality"""
    domain = domain.lower()
    ranks = {
        '.com': 1,    # Most preferred
        '.io': 2,
        '.ai': 3,
        '.net': 4,
        '.org': 5,
        '.co': 6,
        '.tech': 7,
        '.biz': 8     # Least preferred
        # No .other rank - will default to picking left company
    }
    
    for ext in ranks:
        if domain.endswith(ext):
            return ranks[ext]
    return None  # Return None for unranked domains

def process_duplicates(driver, pairs_to_process, auto_reject_errors=False):
    try:
        # Track companies we've already tried to merge
        merged_companies = set()
        
        # Pre-compile XPath expressions for better performance
        ERROR_MODAL_XPATH = "//h4[text()='All is not lost.']"
        CANCEL_BUTTON_XPATH = "//div[contains(@class, 'modal-dialog')]//footer//button[contains(text(), 'Cancel')]"
        
        # Find all Review buttons using the exact attributes from your HTML
        review_buttons = WebDriverWait(driver, 3).until(  # Reduced timeout
            EC.presence_of_all_elements_located((
                By.CSS_SELECTOR, 
                "button[data-test-id='reviewDuplicates']"
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
                
                # Get current review button and row
                try:
                    current_review_button = driver.find_element(By.CSS_SELECTOR, "button[data-test-id='reviewDuplicates']")
                    current_row = current_review_button.find_element(By.XPATH, "./ancestor::tr[1]")
                except:
                    # If not found immediately, wait and try again
                    current_review_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((
                            By.CSS_SELECTOR, 
                            "button[data-test-id='reviewDuplicates']"
                        ))
                    )
                    current_row = current_review_button.find_element(By.XPATH, "./ancestor::tr[1]")
                
                # Get company names efficiently
                try:
                    company1 = current_row.find_element(By.CSS_SELECTOR, "td:nth-child(2) a").text
                    company2 = current_row.find_element(By.CSS_SELECTOR, "td:nth-child(3) a").text
                    company_pair = frozenset([company1, company2])
                    print(f"Comparing: {company1} vs {company2}")
                    
                    if company_pair in merged_companies:
                        print(f"⚠️ These companies were already processed")
                        reject_button = current_row.find_element(By.CSS_SELECTOR, "button[data-test-id='rejectButton']")
                        driver.execute_script("arguments[0].click();", reject_button)
                        time.sleep(0.3)  # Minimal wait
                        continue
                    
                except Exception as e:
                    print(f"Warning: Could not get company names: {str(e)}")
                    company_pair = None
                
                # Scroll and click review button efficiently
                driver.execute_script("""
                    arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});
                    arguments[0].click();
                """, current_review_button)
                time.sleep(0.5)  # Minimal wait for modal
                
                # Check for immediate error modal
                try:
                    error_modal = WebDriverWait(driver, 1).until(  # Reduced timeout
                        EC.presence_of_element_located((By.XPATH, ERROR_MODAL_XPATH))
                    )
                    
                    if error_modal:
                        print("⚠️ Found error modal")
                        cancel_button = driver.find_element(By.XPATH, CANCEL_BUTTON_XPATH)
                        driver.execute_script("arguments[0].click();", cancel_button)
                        time.sleep(0.3)
                        
                        reject_button = current_row.find_element(By.CSS_SELECTOR, "button[data-test-id='rejectButton']")
                        driver.execute_script("arguments[0].click();", reject_button)
                        time.sleep(0.3)
                        continue
                        
                except TimeoutException:
                    # No error modal - proceed with merge
                    try:
                        merge_button = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((
                                By.CSS_SELECTOR,
                                "button[data-test-id='merge-modal-lib_merge-button']"
                            ))
                        )
                        driver.execute_script("arguments[0].click();", merge_button)
                        time.sleep(1)  # Wait for potential error
                        
                        # Check for error after merge
                        try:
                            error_modal = driver.find_element(By.XPATH, ERROR_MODAL_XPATH)
                            if error_modal.is_displayed():
                                print("⚠️ Error after merge attempt")
                                cancel_button = driver.find_element(By.XPATH, CANCEL_BUTTON_XPATH)
                                driver.execute_script("arguments[0].click();", cancel_button)
                                time.sleep(0.3)
                                
                                reject_button = current_row.find_element(By.CSS_SELECTOR, "button[data-test-id='rejectButton']")
                                driver.execute_script("arguments[0].click();", reject_button)
                                time.sleep(0.3)
                            else:
                                raise Exception("Modal not visible")
                                
                        except:
                            print("✅ Merge completed successfully")
                            if company_pair:
                                merged_companies.add(company_pair)
                            time.sleep(0.5)
                            
                    except Exception as e:
                        print(f"Error during merge: {str(e)}")
                        continue
                
            except Exception as e:
                print(f"Error processing pair {i + 1}: {str(e)}")
                proceed = input("Continue with next pair? (y/n): ")
                if proceed.lower() != 'y':
                    return False
                continue
        
        return True
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

def automate_merge():
    print("Starting automation - Chrome browser will open shortly...")
    
    # Setup browser once
    driver = setup_browser()
    if not driver:
        return
    
    try:
        print("\nOpening HubSpot duplicates page...")
        driver.get("https://app.hubspot.com/duplicates/22104039/companies")
        
        print("\nWaiting for you to log in manually and navigate to the duplicates page...")
        print("Please log in through the browser if needed.")
        
        # More efficient page load check
        WebDriverWait(driver, 60).until(
            lambda x: "duplicates" in x.current_url and "login" not in x.current_url
        )
        
        # Main processing loop
        while True:
            print("\nDetected that you're on the duplicates page!")
            pairs_to_process = get_user_input()
            
            success = process_duplicates(driver, pairs_to_process)
            
            if not success:
                print("\nProcessing stopped due to an error or user request.")
            
            # Ask if user wants to process more
            another_batch = input("\nWould you like to process another batch? (y/n): ")
            if another_batch.lower() != 'y':
                break
            
            # Refresh the page to get updated list of duplicates
            print("\nRefreshing page to get updated duplicate list...")
            driver.refresh()
            # Wait for page to be interactive rather than using sleep
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-test-id='reviewDuplicates']"))
            )
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        keep_open = input("\nWould you like to keep the browser open? (y/n): ")
        if keep_open.lower() != 'y':
            driver.quit()
        else:
            print("\nBrowser will remain open. You can close it manually when done.")

if __name__ == "__main__":
    automate_merge() 