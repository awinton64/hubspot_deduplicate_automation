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
import sys
import termios
import tty
from selenium.common.exceptions import TimeoutException
from tqdm import tqdm  # For progress bars

def get_single_keypress():
    """Get a single keypress without requiring Enter"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def parse_args():
    parser = argparse.ArgumentParser(description='HubSpot Duplicate Company Automation')
    
    # Profile management
    parser.add_argument('--profile', help='Chrome profile name to use')
    parser.add_argument('--list-profiles', action='store_true', help='List available Chrome profiles and exit')
    parser.add_argument('--save-last-profile', action='store_true', help='Save the selected profile as default')
    
    # Processing options
    parser.add_argument('--pairs', type=int, help='Number of pairs to process')
    parser.add_argument('--batch-size', type=int, default=20, help='Number of pairs to process in each batch')
    
    # Debug mode (replaces multiple flags)
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging and merge verification')
    
    # Browser options
    parser.add_argument('--keep-open', action='store_true', help='Keep browser open after completion')
    
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
    debug_mode = args and args.debug
    
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
    if last_profile and last_profile in profile_map:
        use_last = input(f"\nUse last profile '{last_profile}'? (Y/n): ").lower()
        if use_last != 'n':
            return profile_map[last_profile], last_profile
    
    # Interactive profile selection
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
    print("Enter number of pairs to process (or press any key to cancel): ", end='', flush=True)
    # Get first keypress
    ch = get_single_keypress()
    
    # If it's not a number, treat as cancel
    if not ch.isdigit():
        print("\nCancelling...")
        return None
    
    # If it is a number, collect the full number
    number = ch
    print(ch, end='', flush=True)  # Echo the first digit
    
    while True:
        ch = get_single_keypress()
        if ch == '\r':  # Enter key
            print()  # New line after input
            break
        if ch.isdigit():  # Add digit to number
            number += ch
            print(ch, end='', flush=True)  # Echo the digit
    
    try:
        total = int(number)
        if total <= 0:
            print("Please enter a positive number")
            return None
        return total
    except ValueError:
        return None  # Return None to indicate cancellation

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

def process_duplicates(driver, pairs_to_process, progress_bar=None, args=None):
    try:
        merged_companies = set()
        processed_count = 0
        debug_mode = args and args.debug
        
        while processed_count < pairs_to_process:
            try:
                if debug_mode:
                    print(f"\nProcessing pair {processed_count + 1} of {pairs_to_process}...")
                
                # Get current row and company names using data-test-id
                current_row = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'tr[data-test-id^="doppel-row-"]'))
                )
                company1 = current_row.find_element(By.CSS_SELECTOR, 'td[data-test-id="doppelganger_ui-record-cell"] a[data-test-id="recordLink"]').text
                company2 = current_row.find_elements(By.CSS_SELECTOR, 'td[data-test-id="doppelganger_ui-record-cell"] a[data-test-id="recordLink"]')[1].text
                company_pair = frozenset([company1, company2])
                
                if debug_mode:
                    print(f"Comparing: {company1} vs {company2}")
                
                # Step 1: Check if already processed
                if company_pair in merged_companies:
                    if debug_mode:
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
                if debug_mode:
                    print("\nOpening review modal...")
                review_button = current_row.find_element(By.XPATH, ".//button[.//i18n-string[@data-key='duplicates.openReviewModal']]")
                driver.execute_script("arguments[0].click();", review_button)
                
                # Step 3: Extract and compare information
                if debug_mode:
                    print("\nExtracting company information...")
                
                # Get contact counts with retries
                contact_counts = get_contact_counts(driver)
                if not contact_counts:
                    if debug_mode:
                        print("❌ Failed to get contact counts after all retries")
                    cancel_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')]")
                    driver.execute_script("arguments[0].click();", cancel_button)
                    if progress_bar:
                        progress_bar.update(1)
                    continue
                
                left_contacts, right_contacts = contact_counts
                
                # Get domains (quick check, don't wait if not immediately available)
                left_domain, right_domain = get_company_domains(driver)
                
                if debug_mode:
                    print(f"\nContact Counts:")
                    print(f"Left company: {left_contacts} contacts")
                    print(f"Right company: {right_contacts} contacts")
                    
                    if left_domain or right_domain:
                        print(f"\nDomains:")
                        print(f"Left company: {left_domain}")
                        print(f"Right company: {right_domain}")
                
                # Step 4: Make selection decision
                if debug_mode:
                    print("\nMaking selection decision...")
                select_right = False
                
                # First check contact counts
                if left_contacts > right_contacts:
                    if debug_mode:
                        print(f"Left company has more contacts ({left_contacts} > {right_contacts})")
                    select_right = False
                elif right_contacts > left_contacts:
                    if debug_mode:
                        print(f"Right company has more contacts ({right_contacts} > {left_contacts})")
                    select_right = True
                else:
                    # If contact counts are tied or both '--', check domains
                    if debug_mode:
                        print("Contact counts are equal or both '--', checking domains...")
                    if left_domain == right_domain or (left_domain == '--' and right_domain == '--'):
                        if debug_mode:
                            print("Domains are same or both '--', selecting left company")
                        select_right = False
                    else:
                        # Compare domain ranks
                        left_rank = get_domain_rank(left_domain)
                        right_rank = get_domain_rank(right_domain)
                        if left_rank is not None and right_rank is not None:
                            if left_rank < right_rank:  # Lower rank is better
                                if debug_mode:
                                    print(f"Left domain has better rank ({left_rank} < {right_rank})")
                                select_right = False
                            else:
                                if debug_mode:
                                    print(f"Right domain has better or equal rank ({right_rank} <= {left_rank})")
                                select_right = True
                        else:
                            if debug_mode:
                                print("One or both domains unranked, selecting left company")
                            select_right = False
                
                # Step 5: Select company and confirm
                current = get_current_selection(driver)
                desired = 'right' if select_right else 'left'
                
                if current != desired:
                    if debug_mode:
                        print(f"\nChanging selection from {current} to {desired} company")
                    select_primary_company(driver, select_right)
                elif debug_mode:
                    print(f"\nKeeping current selection ({current} company)")
                
                # Step 6: Ask for confirmation in debug mode
                if debug_mode:
                    print("\nCurrent Selection Summary:")
                    print("-" * 50)
                    print(f"Selected Company: {desired.upper()}")
                    print(f"Contact Counts: Left ({left_contacts}) vs Right ({right_contacts})")
                    print(f"Domains: Left ({left_domain}) vs Right ({right_domain})")
                    print("-" * 50)
                    print("\nPress Enter to merge, any other key to cancel...")
                    
                    if get_single_keypress() != '\r':  # \r is Enter key
                        print("Canceling merge...")
                        # Refresh page and wait for it to load
                        driver.refresh()
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-test-id='reviewDuplicates']"))
                        )
                        # Reset progress and ask for new batch size
                        if progress_bar:
                            progress_bar.close()
                        return False  # This will trigger asking for new batch size
                
                # Step 7: Execute merge
                if debug_mode:
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
                if debug_mode:
                    print("✅ Merge completed successfully")
                
                if progress_bar:
                    progress_bar.update(1)
                
            except Exception as e:
                if debug_mode:
                    print(f"❌ Error processing pair: {str(e)}")
                try:
                    # Try to find the close button by its aria-label
                    close_button = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Close']"))
                    )
                    driver.execute_script("arguments[0].click();", close_button)
                    
                    # Wait for modal to close
                    WebDriverWait(driver, 3).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.private-modal"))
                    )
                except:
                    # If can't find close button, try clicking outside the modal to close it
                    try:
                        driver.execute_script("""
                            document.querySelector('div.private-modal__backdrop').click();
                        """)
                    except:
                        pass  # Modal might already be closed
                
                if progress_bar:
                    progress_bar.update(1)
                processed_count += 1
                continue
        
        return True
            
    except Exception as e:
        if debug_mode:
            print(f"❌ An error occurred: {str(e)}")
        return False

def automate_merge():
    # Parse command line arguments
    args = parse_args()
    debug_mode = args and args.debug
    
    if debug_mode:
        print("Starting automation in debug mode - Chrome browser will open shortly...")
    else:
        print("Starting automation - Chrome browser will open shortly...")
    
    # Setup browser once
    driver = setup_browser(args)
    if not driver:
        return
    
    try:
        if debug_mode:
            print("\nOpening HubSpot duplicates page...")
        driver.get("https://app.hubspot.com/duplicates/22104039/companies")
        
        if debug_mode:
            print("\nWaiting for you to log in manually and navigate to the duplicates page...")
            print("Please log in through the browser if needed.")
        
        # More efficient page load check
        WebDriverWait(driver, 60).until(
            lambda x: "duplicates" in x.current_url and "login" not in x.current_url
        )
        
        # Main processing loop
        while True:
            if debug_mode:
                print("\nDetected that you're on the duplicates page!")
            
            # Get number of pairs to process
            pairs_to_process = args.pairs or get_user_input()
            if pairs_to_process is None:  # User cancelled
                break
            
            # Process in batches with progress bar
            with tqdm(total=pairs_to_process, disable=not debug_mode) as pbar:
                success = process_duplicates(
                    driver=driver,
                    pairs_to_process=pairs_to_process,
                    progress_bar=pbar,
                    args=args
                )
            
            if not success:
                # If process_duplicates returns False, user cancelled during processing
                continue
            
            # Refresh the page to get updated list of duplicates
            if debug_mode:
                print("\nRefreshing page to get updated duplicate list...")
            driver.refresh()
            # Wait for page to be interactive
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-test-id='reviewDuplicates']"))
            )
        
    except Exception as e:
        if debug_mode:
            import traceback
            print(f"\n❌ Error details:\n{traceback.format_exc()}")
        else:
            print(f"\n❌ An error occurred: {str(e)}")
    finally:
        if args.keep_open:
            if debug_mode:
                print("\nBrowser will remain open. You can close it manually when done.")
        else:
            keep_open = input("\nWould you like to keep the browser open? (y/n): ")
            if keep_open.lower() != 'y':
                driver.quit()
            else:
                print("\nBrowser will remain open. You can close it manually when done.")

if __name__ == "__main__":
    automate_merge() 