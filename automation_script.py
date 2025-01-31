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
import argparse
from pathlib import Path
from selenium.common.exceptions import TimeoutException
from tqdm import tqdm  # For progress bars

def parse_args():
    parser = argparse.ArgumentParser(description='HubSpot Duplicate Company Automation')
    
    # Profile management
    parser.add_argument('--profile', help='Chrome profile name to use')
    parser.add_argument('--list-profiles', action='store_true', help='List available Chrome profiles and exit')
    parser.add_argument('--save-last-profile', action='store_true', help='Save the selected profile as default')
    
    # Processing options
    parser.add_argument('--pairs', type=int, help='Number of pairs to process')
    parser.add_argument('--auto-reject-errors', action='store_true', help='Automatically reject pairs with errors')
    parser.add_argument('--non-interactive', action='store_true', help='Run without asking for confirmation')
    parser.add_argument('--batch-size', type=int, default=20, help='Number of pairs to process in each batch')
    
    # Output options
    parser.add_argument('--quiet', action='store_true', help='Minimize output, show only important messages')
    parser.add_argument('--debug', action='store_true', help='Show detailed debug information')
    parser.add_argument('--log-file', help='Save detailed log to file')
    
    # Browser options
    parser.add_argument('--keep-open', action='store_true', help='Keep browser open after completion')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode (no GUI)')
    
    return parser.parse_args()

def get_config_dir():
    """Get or create config directory"""
    config_dir = Path.home() / '.hubspot_dedup'
    config_dir.mkdir(exist_ok=True)
    return config_dir

def save_last_profile(profile_name):
    """Save last used profile"""
    config_file = get_config_dir() / 'last_profile'
    config_file.write_text(profile_name)

def get_last_profile():
    """Get last used profile"""
    config_file = get_config_dir() / 'last_profile'
    if config_file.exists():
        return config_file.read_text().strip()
    return None

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

def list_and_select_profile(args):
    """List and select Chrome profile with command line arg support"""
    profiles = get_chrome_profiles()
    
    if not profiles:
        print("No Chrome profiles found!")
        return None, None
    
    # Create a mapping of profile names to directories
    profile_map = {
        info.get('name', 'Unnamed'): dir_name 
        for dir_name, info in profiles.items()
    }
    
    # If --list-profiles, just show profiles and exit
    if args.list_profiles:
        print("\nAvailable Chrome profiles:")
        print("-" * 50)
        for name in profile_map.keys():
            print(f"  {name}")
        print("-" * 50)
        return None, None
    
    # If --profile is specified, use that
    if args.profile:
        if args.profile in profile_map:
            if args.save_last_profile:
                save_last_profile(args.profile)
            return profile_map[args.profile], args.profile
        else:
            print(f"Error: Profile '{args.profile}' not found")
            return None, None
    
    # Try to use last profile if no profile specified
    last_profile = get_last_profile()
    if last_profile and last_profile in profile_map and not args.quiet:
        use_last = input(f"\nUse last profile '{last_profile}'? (Y/n): ").lower()
        if use_last != 'n':
            return profile_map[last_profile], last_profile
    
    # Interactive profile selection
    if not args.non_interactive:
        print("\nAvailable Chrome profiles:")
        print("-" * 50)
        
        # Create a list of profiles for easy selection
        profile_list = list(profile_map.items())
        for idx, (name, dir_name) in enumerate(profile_list, 1):
            print(f"{idx}. {name}")
        
        print("-" * 50)
        
        while True:
            try:
                choice = int(input("\nSelect a profile number (or 0 to exit): "))
                if choice == 0:
                    return None, None
                if 1 <= choice <= len(profile_list):
                    selected_profile = profile_list[choice-1]
                    if args.save_last_profile:
                        save_last_profile(selected_profile[0])
                    return selected_profile[1], selected_profile[0]
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    print("No profile selected")
    return None, None

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

def setup_browser(args):
    # Get Chrome profile
    profile_dir, profile_name = list_and_select_profile(args)
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
        # Quick check for boxes and their state
        boxes = WebDriverWait(driver, 2).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.private-selectable-box.private-selectable-button"))
        )
        
        # Direct check of aria-checked attribute
        for i, box in enumerate(boxes):
            if box.get_attribute('aria-checked') == 'true':
                result = 'right' if i == 1 else 'left'
                print(f"  ✅ {result.upper()} box is selected")
                return result
                
        print("  ⚠️ No selection found, defaulting to LEFT")
        return 'left'
    except Exception as e:
        print(f"  ❌ Error checking selection: {str(e)}")
        return 'left'

def select_primary_company(driver, select_right):
    """Select either the left or right company as primary"""
    try:
        print("\n🎯 Selecting primary company...")
        desired = "RIGHT" if select_right else "LEFT"
        
        def quick_select():
            try:
                # Get boxes with minimal wait
                boxes = WebDriverWait(driver, 1).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.private-selectable-box.private-selectable-button"))
                )
                
                if len(boxes) != 2:
                    return False, "Wrong number of boxes"
                    
                target_box = boxes[1] if select_right else boxes[0]
                
                # Check if already selected
                if target_box.get_attribute('aria-checked') == 'true':
                    return True, "Already selected"
                
                # Direct click without scrolling (HubSpot's modal is always visible)
                driver.execute_script("arguments[0].click();", target_box)
                
                # Quick check for success
                return (target_box.get_attribute('aria-checked') == 'true', "Click executed")
                
            except Exception as e:
                return False, str(e)
        
        # Fast retry loop
        max_attempts = 3
        for attempt in range(max_attempts):
            success, message = quick_select()
            
            if success:
                print(f"  ✅ {message}")
                return
                
            if attempt < max_attempts - 1:
                print(f"  ⚠️ Attempt {attempt + 1} failed: {message}")
                time.sleep(0.2)  # Very short delay between attempts
        
        raise Exception(f"Failed to select {desired} company")
        
    except Exception as e:
        print(f"  ❌ Selection failed: {str(e)}")
        raise e

def get_company_domains(driver):
    """Get domains from both companies in merge modal"""
    try:
        # Try to get domains with a very short timeout first
        try:
            domain_elements = WebDriverWait(driver, 0.5).until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    "div.merge-select-object div[data-test-id='domain-name'] div.private-truncated-string__inner"  # More specific selector
                ))
            )
            
            if len(domain_elements) == 2:
                left_domain = domain_elements[0].text.strip()
                right_domain = domain_elements[1].text.strip()
                return left_domain, right_domain
        except:
            pass  # If quick attempt fails, return None values
            
        return None, None
        
    except Exception as e:
        print(f"Error getting company domains: {str(e)}")
        return None, None

def process_duplicates(driver, pairs_to_process, auto_reject_errors=False, progress_bar=None, args=None):
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
                    if progress_bar:
                        progress_bar.update(1)
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
                        if progress_bar:
                            progress_bar.update(1)
                        continue
                    proceed = input("Continue with next pair? (y/n): ")
                    if proceed.lower() != 'y':
                        return False
                    if progress_bar:
                        progress_bar.update(1)
                    continue
                
                left_contacts, right_contacts = contact_counts
                
                # Get domains (quick check, don't wait if not immediately available)
                left_domain, right_domain = get_company_domains(driver)
                
                print(f"\nContact Counts:")
                print(f"Left company: {left_contacts} contacts")
                print(f"Right company: {right_contacts} contacts")
                
                if left_domain or right_domain:  # Only print domain info if we found any
                    print(f"\nDomains:")
                    print(f"Left company: {left_domain}")
                    print(f"Right company: {right_domain}")
                
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
                    if progress_bar:
                        progress_bar.update(1)
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
                
                if progress_bar:
                    progress_bar.update(1)
                
            except Exception as e:
                print(f"❌ Error processing pair: {str(e)}")
                if auto_reject_errors:
                    print("Auto-rejecting this pair...")
                    try:
                        cancel_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
                        driver.execute_script("arguments[0].click();", cancel_button)
                    except:
                        pass  # Modal might already be closed
                    if progress_bar:
                        progress_bar.update(1)
                    continue
                proceed = input("Continue with next pair? (y/n): ")
                if proceed.lower() != 'y':
                    return False
                if progress_bar:
                    progress_bar.update(1)
                continue
        
        return True
            
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        return False

def automate_merge():
    # Parse command line arguments
    args = parse_args()
    
    # Setup logging if requested
    if args.log_file:
        import logging
        logging.basicConfig(
            filename=args.log_file,
            level=logging.DEBUG if args.debug else logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    if not args.quiet:
        print("Starting automation - Chrome browser will open shortly...")
    
    # Setup browser once
    driver = setup_browser(args)
    if not driver:
        return
    
    try:
        if not args.quiet:
            print("\nOpening HubSpot duplicates page...")
        driver.get("https://app.hubspot.com/duplicates/22104039/companies")
        
        if not args.quiet:
            print("\nWaiting for you to log in manually and navigate to the duplicates page...")
            print("Please log in through the browser if needed.")
        
        # More efficient page load check
        WebDriverWait(driver, 60).until(
            lambda x: "duplicates" in x.current_url and "login" not in x.current_url
        )
        
        # Main processing loop
        while True:
            if not args.quiet:
                print("\nDetected that you're on the duplicates page!")
            
            # Get number of pairs to process
            pairs_to_process = args.pairs or get_user_input() if not args.non_interactive else args.batch_size
            
            # Process in batches with progress bar
            with tqdm(total=pairs_to_process, disable=args.quiet) as pbar:
                success = process_duplicates(
                    driver=driver,
                    pairs_to_process=pairs_to_process,
                    auto_reject_errors=args.auto_reject_errors,
                    progress_bar=pbar,
                    args=args
                )
            
            if not success:
                if not args.quiet:
                    print("\nProcessing stopped due to an error or user request.")
            
            # In non-interactive mode, we're done
            if args.non_interactive:
                break
            
            # Ask if user wants to process more
            another_batch = input("\nWould you like to process another batch? (y/n): ")
            if another_batch.lower() != 'y':
                break
            
            # Refresh the page to get updated list of duplicates
            if not args.quiet:
                print("\nRefreshing page to get updated duplicate list...")
            driver.refresh()
            # Wait for page to be interactive
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-test-id='reviewDuplicates']"))
            )
        
    except Exception as e:
        if args.debug:
            import traceback
            print(f"\n❌ Error details:\n{traceback.format_exc()}")
        else:
            print(f"\n❌ An error occurred: {str(e)}")
    finally:
        if args.keep_open:
            if not args.quiet:
                print("\nBrowser will remain open. You can close it manually when done.")
        else:
            if not args.non_interactive and not args.quiet:
                keep_open = input("\nWould you like to keep the browser open? (y/n): ")
                if keep_open.lower() != 'y':
                    driver.quit()
                else:
                    print("\nBrowser will remain open. You can close it manually when done.")
            else:
                driver.quit()

if __name__ == "__main__":
    automate_merge() 