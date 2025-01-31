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
        print("\n📊 Getting contact counts...")
        
        def is_valid_text(text):
            text = text.strip()
            return text.isdigit() or text == '--' or text == ''
        
        def get_counts():
            try:
                # Quick modal check
                WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.private-modal"))
                )
                
                # Get contact elements
                contact_elements = WebDriverWait(driver, 1).until(
                    EC.presence_of_all_elements_located((
                        By.XPATH,
                        "//dt[text()='Number of Associated Contacts']/following-sibling::dd[1]//span[contains(@class, 'private-truncated-string__inner')]"
                    ))
                )
                
                if len(contact_elements) != 2:
                    return None, None, "Wrong number of elements found"
                
                left_text = contact_elements[0].text.strip()
                right_text = contact_elements[1].text.strip()
                
                # Handle empty strings
                if left_text == '' or right_text == '':
                    return None, None, "Empty values found"
                
                if not is_valid_text(left_text) or not is_valid_text(right_text):
                    return None, None, "Invalid values found"
                
                # Convert to numbers
                left_contacts = 0 if left_text == '--' else int(left_text)
                right_contacts = 0 if right_text == '--' else int(right_text)
                
                return left_contacts, right_contacts, "Success"
                
            except Exception as e:
                return None, None, str(e)
        
        # Main retry loop
        max_attempts = 5  # Keep 5 retries for contact counts
        for attempt in range(max_attempts):
            print(f"  Attempt {attempt + 1}/{max_attempts}...")
            left, right, message = get_counts()
            
            if left is not None and right is not None:
                print(f"  ✅ Found valid counts: Left({left}) Right({right})")
                return left, right
            
            print(f"  ⚠️ {message}, retrying...")
            if attempt < max_attempts - 1:
                time.sleep(0.5)  # Short delay between retries
        
        raise Exception(f"Failed to get valid contact counts after {max_attempts} attempts")
        
    except Exception as e:
        print(f"  ❌ Error getting contact counts: {str(e)}")
        return None, None

def get_current_selection(driver):
    """Get which company (left/right) is currently selected"""
    try:
        print("\n🔍 Checking current selection...")
        # Wait for modal and boxes to be fully loaded
        print("  Waiting for selectable boxes to load...")
        boxes = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.private-selectable-box.private-selectable-button"))
        )
        print(f"  Found {len(boxes)} selectable boxes")
        
        # Check which box is selected using aria-checked attribute
        for i, box in enumerate(boxes):
            aria_checked = box.get_attribute('aria-checked')
            print(f"  Box {i+1}: aria-checked = {aria_checked}")
            if aria_checked == 'true':
                result = 'right' if i == 1 else 'left'
                print(f"  ✅ Found selection: {result.upper()} box is selected")
                return result
        print("  ⚠️ No box found with aria-checked='true', defaulting to LEFT")
        return 'left'  # Default to left if can't determine
    except Exception as e:
        print(f"  ❌ Error getting current selection: {str(e)}")
        return 'left'  # Default to left if can't determine

def select_primary_company(driver, select_right):
    """Select either the left or right company as primary"""
    try:
        print("\n🎯 Attempting to select primary company...")
        desired = "RIGHT" if select_right else "LEFT"
        print(f"  Target: {desired} company")
        
        def verify_selection(box):
            try:
                return (
                    box.get_attribute('aria-checked') == 'true' and
                    len(driver.find_elements(By.CSS_SELECTOR, "div.private-loading-spinner")) == 0
                )
            except:
                return False
        
        def attempt_selection():
            try:
                # Quick check for modal
                modal = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.private-modal[aria-modal='true']"))
                )
                
                # Get both boxes in one go
                boxes = WebDriverWait(driver, 2).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.private-selectable-box.private-selectable-button"))
                )
                
                if len(boxes) != 2:
                    return False, "Wrong number of boxes found"
                
                target_box = boxes[1] if select_right else boxes[0]
                
                # Quick check if already selected
                if verify_selection(target_box):
                    return True, "Already selected correctly"
                
                # Click and verify
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", target_box)
                
                # Quick verification
                if WebDriverWait(driver, 1).until(lambda _: verify_selection(target_box)):
                    return True, "Selection successful"
                
                return False, "Selection failed verification"
                
            except Exception as e:
                return False, str(e)
        
        # Main retry loop
        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"  Attempt {attempt + 1}/{max_attempts}...")
            success, message = attempt_selection()
            
            if success:
                print(f"  ✅ {message}")
                return
            
            print(f"  ⚠️ {message}, retrying...")
            if attempt < max_attempts - 1:
                time.sleep(0.5)  # Short delay between retries
        
        raise Exception(f"Failed to select {desired} company after {max_attempts} attempts")
    except Exception as e:
        print(f"  ❌ Error selecting primary company: {str(e)}")
        raise e

def get_company_domains(driver):
    """Get domains from both companies in merge modal"""
    try:
        # Find domain elements in the merge modal using a more specific selector
        domain_elements = WebDriverWait(driver, 3).until(  # Reduced from 5 to 3 seconds
            EC.presence_of_all_elements_located((
                By.CSS_SELECTOR,
                "div.merge-select-object div.private-truncated-string__inner"  # More specific CSS selector
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
                
                # Step 3: Extract and compare information
                print("\nExtracting company information...")
                
                # Get contact counts with retries
                contact_counts = get_contact_counts(driver)
                if not contact_counts:
                    print("❌ Failed to get contact counts after all retries")
                    if auto_reject_errors:
                        print("Auto-rejecting this pair...")
                        cancel_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
                        driver.execute_script("arguments[0].click();", cancel_button)
                        continue
                    proceed = input("Continue with next pair? (y/n): ")
                    if proceed.lower() != 'y':
                        return False
                    continue
                
                left_contacts, right_contacts = contact_counts
                
                # Get domains
                left_domain, right_domain = get_company_domains(driver)
                
                print(f"\nContact Counts:")
                print(f"Left company: {left_contacts} contacts")
                print(f"Right company: {right_contacts} contacts")
                
                print(f"\nDomains:")
                print(f"Left company: {left_domain} (rank: {get_domain_rank(left_domain) if left_domain else None})")
                print(f"Right company: {right_domain} (rank: {get_domain_rank(right_domain) if right_domain else None})")
                
                # Step 4: Make selection decision
                print("\nMaking selection decision...")
                select_right = False
                
                # First check contact counts
                if left_contacts > right_contacts:
                    print(f"Left company has more contacts ({left_contacts} > {right_contacts})")
                    select_right = False
                elif right_contacts > left_contacts:
                    print(f"Right company has more contacts ({right_contacts} > {left_contacts})")
                    select_right = True
                else:
                    # If contact counts are tied or both '--', check domains
                    print("Contact counts are equal or both '--', checking domains...")
                    if left_domain == right_domain or (left_domain == '--' and right_domain == '--'):
                        print("Domains are same or both '--', selecting left company")
                        select_right = False
                    else:
                        # Compare domain ranks
                        left_rank = get_domain_rank(left_domain)
                        right_rank = get_domain_rank(right_domain)
                        if left_rank is not None and right_rank is not None:
                            if left_rank < right_rank:  # Lower rank is better
                                print(f"Left domain has better rank ({left_rank} < {right_rank})")
                                select_right = False
                            else:
                                print(f"Right domain has better or equal rank ({right_rank} <= {left_rank})")
                                select_right = True
                        else:
                            print("One or both domains unranked, selecting left company")
                            select_right = False
                
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
                print(f"❌ Error processing pair: {str(e)}")
                if auto_reject_errors:
                    print("Auto-rejecting this pair...")
                    try:
                        cancel_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
                        driver.execute_script("arguments[0].click();", cancel_button)
                    except:
                        pass  # Modal might already be closed
                    continue
                proceed = input("Continue with next pair? (y/n): ")
                if proceed.lower() != 'y':
                    return False
                continue
        
        return True
            
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
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