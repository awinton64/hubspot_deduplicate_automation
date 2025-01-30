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

def get_contact_counts(driver):
    """Get contact counts from both companies in merge modal"""
    try:
        # Wait for the contact count elements to be present
        contact_elements = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((
                By.XPATH,
                "//div[contains(@class, 'merge-select-object')]//div[contains(text(), 'Associated contacts')]/following-sibling::div"
            ))
        )
        
        if len(contact_elements) != 2:
            print("⚠️ Could not find contact counts for both companies")
            return None, None
        
        # Extract numbers from text (e.g., "5 contacts" -> 5)
        left_contacts = int(contact_elements[0].text.split()[0])
        right_contacts = int(contact_elements[1].text.split()[0])
        
        print(f"Left company contacts: {left_contacts}")
        print(f"Right company contacts: {right_contacts}")
        
        return left_contacts, right_contacts
        
    except Exception as e:
        print(f"Error getting contact counts: {str(e)}")
        return None, None

def get_current_selection(driver):
    """Get which company (left/right) is currently selected"""
    try:
        # Wait for modal and boxes to be fully loaded
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.private-selectable-box"))
        )
        
        # Check which box is selected using the class
        boxes = driver.find_elements(By.CSS_SELECTOR, "div.private-selectable-box")
        for i, box in enumerate(boxes):
            if 'private-selectable-box--selected' in box.get_attribute('class'):
                return 'right' if i == 1 else 'left'
        return 'left'  # Default to left if can't determine
    except Exception as e:
        print(f"Error getting current selection: {str(e)}")
        return 'left'  # Default to left if can't determine

def select_primary_company(driver, select_right):
    """Select either the left or right company as primary"""
    try:
        # Wait for boxes to be clickable
        boxes = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.private-selectable-box"))
        )
        if len(boxes) != 2:
            raise Exception("Could not find both company boxes")
            
        # Select the target box
        target_box = boxes[1] if select_right else boxes[0]
        
        # Click the box and wait for selection to update
        driver.execute_script("arguments[0].click();", target_box)
        WebDriverWait(driver, 3).until(
            lambda x: ('private-selectable-box--selected' in target_box.get_attribute('class'))
        )
        
    except Exception as e:
        print(f"Error selecting primary company: {str(e)}")
        raise e

def get_company_domains(driver):
    """Get domains from both companies in merge modal"""
    try:
        # Find domain elements in the merge modal
        domain_elements = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((
                By.XPATH,
                "//div[contains(@class, 'merge-select-object')]//div[contains(text(), 'Domain name')]/following-sibling::div"
            ))
        )
        
        if len(domain_elements) != 2:
            print("⚠️ Could not find domains for both companies")
            return None, None
        
        left_domain = domain_elements[0].text.strip()
        right_domain = domain_elements[1].text.strip()
        
        print(f"Left domain: {left_domain}")
        print(f"Right domain: {right_domain}")
        
        return left_domain, right_domain
        
    except Exception as e:
        print(f"Error getting company domains: {str(e)}")
        return None, None

def process_duplicates(driver, pairs_to_process, auto_reject_errors=False):
    try:
        merged_companies = set()
        processed_count = 0
        
        while processed_count < pairs_to_process:
            try:
                print(f"\nProcessing pair {processed_count + 1} of {pairs_to_process}...")
                
                # Get current row and company names using data-test-id
                current_row = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'tr[data-test-id^="doppel-row-"]'))
                )
                company1 = current_row.find_element(By.CSS_SELECTOR, 'td[data-test-id="doppelganger_ui-record-cell"] a[data-test-id="recordLink"]').text
                company2 = current_row.find_elements(By.CSS_SELECTOR, 'td[data-test-id="doppelganger_ui-record-cell"] a[data-test-id="recordLink"]')[1].text
                company_pair = frozenset([company1, company2])
                
                print(f"Comparing: {company1} vs {company2}")
                
                # Step 1: Check if already processed
                if company_pair in merged_companies:
                    print(f"⚠️ These companies were already processed")
                    reject_button = current_row.find_element(By.XPATH, ".//button[.//i18n-string[@data-key='duplicates.table.buttons.reject']]")
                    driver.execute_script("arguments[0].click();", reject_button)
                    WebDriverWait(driver, 3).until(
                        EC.staleness_of(reject_button)
                    )
                    processed_count += 1
                    continue
                
                # Step 2: Click Review to open modal
                print("\nOpening review modal...")
                review_button = current_row.find_element(By.XPATH, ".//button[.//i18n-string[@data-key='duplicates.openReviewModal']]")
                driver.execute_script("arguments[0].click();", review_button)
                
                # Wait for modal to be fully loaded by checking for contact counts
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//dt[text()='Number of Associated Contacts']"))
                )
                
                # Step 3: Extract and compare information
                print("\nExtracting company information...")
                
                # Get contact counts using more reliable selectors
                left_contacts = int(WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                        "//dt[text()='Number of Associated Contacts']/following-sibling::dd[1]//span[contains(@class, 'private-truncated-string__inner')]"))
                ).text)
                
                right_contacts = int(WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                        "(//dt[text()='Number of Associated Contacts']/following-sibling::dd[1]//span[contains(@class, 'private-truncated-string__inner')])[2]"))
                ).text)
                
                print(f"\nContact Counts:")
                print(f"Left company: {left_contacts} contacts")
                print(f"Right company: {right_contacts} contacts")
                
                # Get domains using more reliable selectors
                try:
                    left_domain = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH,
                            "//div[contains(@class, 'private-selectable-box--selected')]//small[contains(@class, 'private-microcopy')]"))
                    ).text.strip('--')
                except:
                    left_domain = None
                    
                try:
                    right_domain = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH,
                            "(//div[contains(@class, 'private-selectable-box')]//small[contains(@class, 'private-microcopy')])[2]"))
                    ).text.strip('--')
                except:
                    right_domain = None
                
                left_rank = get_domain_rank(left_domain) if left_domain else None
                right_rank = get_domain_rank(right_domain) if right_domain else None
                
                print(f"\nDomains:")
                print(f"Left company: {left_domain} (rank: {left_rank})")
                print(f"Right company: {right_domain} (rank: {right_rank})")
                
                # Step 4: Make selection decision
                print("\nMaking selection decision...")
                select_right = False
                
                if left_contacts is not None and right_contacts is not None:
                    if right_contacts > left_contacts * 1.5:
                        print("Right company has 50% more contacts")
                        select_right = True
                    elif left_contacts > right_contacts * 1.5:
                        print("Left company has 50% more contacts")
                        select_right = False
                    else:
                        print("Contact counts similar, checking domains...")
                        if left_rank and right_rank:
                            if right_rank < left_rank:
                                print("Right company has better domain extension")
                                select_right = True
                            elif left_rank < right_rank:
                                print("Left company has better domain extension")
                                select_right = False
                            else:
                                print("Domain ranks equal, keeping left company")
                
                # Step 5: Select company and confirm
                current = get_current_selection(driver)
                desired = 'right' if select_right else 'left'
                
                if current != desired:
                    print(f"\nChanging selection from {current} to {desired} company")
                    select_primary_company(driver, select_right)
                else:
                    print(f"\nKeeping current selection ({current} company)")
                
                # Step 6: Ask for confirmation
                print("\nCurrent Selection Summary:")
                print("-" * 50)
                print(f"Selected Company: {desired.upper()}")
                print(f"Contact Counts: Left ({left_contacts}) vs Right ({right_contacts})")
                print(f"Domains: Left ({left_domain}) vs Right ({right_domain})")
                print("-" * 50)
                
                proceed = input("\nIs this selection correct? (y/n): ")
                if proceed.lower() != 'y':
                    print("Canceling merge...")
                    cancel_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
                    driver.execute_script("arguments[0].click();", cancel_button)
                    continue
                
                # Step 7: Execute merge
                print("\nExecuting merge...")
                merge_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-test-id='merge-modal-lib_merge-button']"))
                )
                driver.execute_script("arguments[0].click();", merge_button)
                
                # Wait for merge to complete by checking for button staleness
                WebDriverWait(driver, 10).until(
                    EC.staleness_of(merge_button)
                )
                
                # Add to processed set and increment counter
                merged_companies.add(company_pair)
                processed_count += 1
                print("✅ Merge completed successfully")
                
            except Exception as e:
                print(f"Error processing pair: {str(e)}")
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