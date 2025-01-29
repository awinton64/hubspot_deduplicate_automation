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
                
                # Wait for the current review button to be present and visible
                current_review_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, f"button[aria-label='Review'][data-test-id='reviewDuplicates']"))
                )
                
                # Get the current row containing the review button
                current_row = current_review_button.find_element(By.XPATH, ".//ancestor::tr")
                
                # Get company names first
                try:
                    company1 = current_row.find_element(By.XPATH, ".//td[2]//div/div[2]/a").text
                    company2 = current_row.find_element(By.XPATH, ".//td[3]//div/div[2]/a").text
                    company_pair = frozenset([company1, company2])
                    print(f"Comparing: {company1} vs {company2}")
                    
                    # Check if we've already tried to merge these companies
                    if company_pair in merged_companies:
                        print(f"⚠️ These companies ({company1} vs {company2}) were already processed in a previous merge")
                        try:
                            # Find reject button using data-test-id
                            reject_button = WebDriverWait(current_row, 10).until(
                                EC.element_to_be_clickable((
                                    By.CSS_SELECTOR, 
                                    "button[data-test-id='rejectButton']"
                                ))
                            )
                            print("Auto-rejecting duplicate merge attempt...")
                            driver.execute_script("arguments[0].click();", reject_button)
                            time.sleep(1)
                            continue
                        except Exception as e:
                            print(f"Error finding reject button: {str(e)}")
                            try:
                                # Try alternative method using XPath
                                reject_button = current_row.find_element(
                                    By.XPATH,
                                    ".//button[contains(@class, 'private-button') and .//i18n-string[text()='Reject']]"
                                )
                                print("Found reject button using alternative method...")
                                driver.execute_script("arguments[0].click();", reject_button)
                                time.sleep(1)
                                continue
                            except Exception as e:
                                print(f"Could not find reject button for {company1} vs {company2} using any method")
                                continue
                    
                except Exception as e:
                    print("Warning: Could not get company names")
                    company1 = "Unknown"
                    company2 = "Unknown"
                    company_pair = None
                
                print("Scrolling to Review button...")
                driver.execute_script("arguments[0].scrollIntoView(true);", current_review_button)
                time.sleep(2)
                
                print("Clicking Review button...")
                current_review_button.click()
                time.sleep(2)  # Wait for modal to appear
                
                # Check for "All is not lost" error modal
                try:
                    error_heading = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//h4[text()='All is not lost.']"))
                    )
                    
                    if error_heading:
                        print("⚠️ Found 'All is not lost' error modal - companies were already merged")
                        # Click Cancel button in the error modal
                        cancel_button = driver.find_element(
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//footer//button[2]"
                        )
                        print("Clicking Cancel button...")
                        driver.execute_script("arguments[0].click();", cancel_button)
                        time.sleep(1)
                        
                        # Now find and click reject button using data-test-id
                        try:
                            reject_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((
                                    By.CSS_SELECTOR,
                                    "button[data-test-id='rejectButton']"
                                ))
                            )
                            print(f"Clicking Reject button for {company1} vs {company2}...")
                            driver.execute_script("arguments[0].click();", reject_button)
                            time.sleep(1)
                        except:
                            print("Could not find reject button with data-test-id, trying alternative method...")
                            try:
                                # Try finding by XPath with text content
                                reject_button = current_row.find_element(
                                    By.XPATH,
                                    ".//button[contains(@class, 'private-button') and .//i18n-string[text()='Reject']]"
                                )
                                print(f"Clicking Reject button (alternative method) for {company1} vs {company2}...")
                                driver.execute_script("arguments[0].click();", reject_button)
                                time.sleep(1)
                            except Exception as e:
                                print(f"Could not find reject button using any method: {str(e)}")
                                continue
                        
                except Exception as e:
                    # No error modal found, proceed with normal merge flow
                    pass
                
                # Normal merge flow continues...
                try:
                    # Click the Merge button
                    merge_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//footer//button[1]"
                        ))
                    )
                    print("🔄 Clicking merge button...")
                    driver.execute_script("arguments[0].click();", merge_button)
                    
                    # Wait a moment for first modal to close and potential error modal to appear
                    time.sleep(3)
                    
                    # Check for error modal that appears after merge attempt
                    try:
                        # Wait specifically for the error modal
                        error_modal = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((
                                By.XPATH, 
                                "//div[contains(@class, 'modal-dialog')]//h4[text()='All is not lost.']"
                            ))
                        )
                        
                        if error_modal:
                            print("⚠️ Error modal appeared after merge attempt")
                            
                            # Wait for and click Cancel button in error modal
                            cancel_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((
                                    By.XPATH,
                                    "//div[contains(@class, 'modal-dialog')]//footer//button[contains(text(), 'Cancel')]"
                                ))
                            )
                            print("Clicking Cancel button on error modal...")
                            driver.execute_script("arguments[0].click();", cancel_button)
                            time.sleep(2)  # Wait for modal to fully close
                            
                            # Now find and click reject button using data-test-id
                            try:
                                reject_button = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((
                                        By.CSS_SELECTOR,
                                        "button[data-test-id='rejectButton']"
                                    ))
                                )
                                print(f"Clicking Reject button for {company1} vs {company2}...")
                                driver.execute_script("arguments[0].click();", reject_button)
                                time.sleep(1)
                            except:
                                print("Could not find reject button with data-test-id, trying alternative method...")
                                try:
                                    # Try finding by XPath with text content
                                    reject_button = current_row.find_element(
                                        By.XPATH,
                                        ".//button[contains(@class, 'private-button') and .//i18n-string[text()='Reject']]"
                                    )
                                    print(f"Clicking Reject button (alternative method) for {company1} vs {company2}...")
                                    driver.execute_script("arguments[0].click();", reject_button)
                                    time.sleep(1)
                                except Exception as e:
                                    print(f"Could not find reject button using any method: {str(e)}")
                                    continue
                            
                    except TimeoutException:
                        # No error modal appeared - merge was successful
                        print("✅ Merge completed successfully")
                        if company_pair:
                            merged_companies.add(company_pair)
                        time.sleep(2)
                        
                except Exception as e:
                    print(f"Error during merge process: {str(e)}")
                    continue
                
            except Exception as e:
                print(f"Error processing pair {i + 1}: {str(e)}")
                proceed = input("Would you like to continue with the next pair? (y/n): ")
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
        
        while True:
            current_url = driver.current_url
            if "duplicates" in current_url and not "login" in current_url:
                break
            time.sleep(2)  # Check every 2 seconds
        
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
            time.sleep(3)
        
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