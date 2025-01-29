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
                print("Scrolling to Review button...")
                
                driver.execute_script("arguments[0].scrollIntoView(true);", review_buttons[i])
                time.sleep(2)
                
                print("Clicking Review button...")
                review_buttons[i].click()
                
                # Wait for the merge dialog to appear and be fully loaded
                time.sleep(3)  # Increased wait time
                
                try:
                    # Wait explicitly for the contact numbers to be visible
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//dt[contains(text(), 'Number of Associated Contacts')]"))
                    )
                    
                    # Find both contact number elements using more reliable XPaths
                    contact_number1 = driver.find_element(
                        By.XPATH,
                        "//div[contains(@class, 'modal-dialog')]//div[contains(@class, 'UIFlex')]//div[1]//dt[contains(text(), 'Number of Associated Contacts')]/following-sibling::dd//span[last()]"
                    )
                    
                    contact_number2 = driver.find_element(
                        By.XPATH,
                        "//div[contains(@class, 'modal-dialog')]//div[contains(@class, 'UIFlex')]//div[2]//dt[contains(text(), 'Number of Associated Contacts')]/following-sibling::dd//span[last()]"
                    )
                    
                    # Extract and compare the numbers
                    num1 = int(contact_number1.text)
                    num2 = int(contact_number2.text)
                    
                    # Get domain extensions for tie-breaker
                    try:
                        # Wait for domains to be visible
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "small.private-microcopy"))
                        )
                        
                        # Get domains using more specific selectors
                        domain1 = driver.find_element(
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//div[2]/div/div[1]//div[contains(@class, 'private-selectable-box')]//small[contains(@class, 'private-microcopy')]"
                        ).text.strip()
                        
                        domain2 = driver.find_element(
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//div[2]/div/div[2]//div[contains(@class, 'private-selectable-box')]//small[contains(@class, 'private-microcopy')]"
                        ).text.strip()
                        
                        # Print raw HTML for debugging domain elements
                        print("\n🔍 Domain Elements HTML:")
                        domain1_elem = driver.find_element(
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//div[2]/div/div[1]//div[contains(@class, 'private-selectable-box')]"
                        )
                        domain2_elem = driver.find_element(
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//div[2]/div/div[2]//div[contains(@class, 'private-selectable-box')]"
                        )
                        print("Left company HTML:", domain1_elem.get_attribute('innerHTML'))
                        print("Right company HTML:", domain2_elem.get_attribute('innerHTML'))
                        
                    except Exception as e:
                        print(f"Error getting domains: {str(e)}")
                        domain1 = ""
                        domain2 = ""
                    
                    # Print raw values for debugging
                    print("\n🔍 Debug Info:")
                    print(f"Raw Left Number Text: '{contact_number1.text}'")
                    print(f"Raw Right Number Text: '{contact_number2.text}'")
                    print(f"Raw Left Domain: '{domain1}'")
                    print(f"Raw Right Domain: '{domain2}'")
                    
                    # Determine which record to pick
                    pick_second = False
                    if num2 > num1:
                        pick_second = True
                    elif num1 == num2:
                        # If tie, compare domain extensions
                        rank1 = get_domain_rank(domain1)
                        rank2 = get_domain_rank(domain2)
                        
                        print("\n🌐 Domain Ranking Debug:")
                        print(f"Left domain ({domain1}) rank: {rank1}")
                        print(f"Right domain ({domain2}) rank: {rank2}")
                        
                        # Only pick second if both domains are ranked and second is better
                        if rank1 is not None and rank2 is not None and rank2 < rank1:
                            pick_second = True
                            print(f"Picking right company because {domain2} (rank {rank2}) is preferred over {domain1} (rank {rank1})")
                        else:
                            print(f"Keeping left company because {domain1} is {'equally or more preferred' if rank1 is not None else 'unranked'}")
                    
                    # Print comparison in a clear, easy to read format
                    print("\n" + "=" * 70)
                    print(f"📊 PROCESSING PAIR {i + 1} OF {pairs_to_process}")
                    print("=" * 70)
                    
                    # Contact comparison
                    print("\n📞 CONTACTS:")
                    print(f"   Left:  {num1} contacts")
                    print(f"   Right: {num2} contacts")
                    winner = "RIGHT" if num2 > num1 else "LEFT" if num1 > num2 else "TIE"
                    print(f"   Winner by contacts: {winner}")
                    
                    # Domain comparison
                    print("\n🌐 DOMAINS:")
                    print(f"   Left:  {domain1}")
                    print(f"   Right: {domain2}")
                    if num1 == num2:
                        if rank1 is not None and rank2 is not None:
                            domain_winner = "RIGHT" if rank2 < rank1 else "LEFT"
                            print(f"   Winner by domain preference: {domain_winner}")
                        else:
                            print("   Using default: LEFT (unranked domains)")
                    
                    # Final decision
                    print("\n🎯 DECISION:")
                    print(f"   {'RIGHT' if pick_second else 'LEFT'} company will be primary")
                    print("=" * 70)
                    
                    # Find and click the card automatically
                    if pick_second:
                        print("⚡ Selecting right company...")
                        radio2 = driver.find_element(
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//div[2]/div/div[2]//input[@type='radio']"
                        )
                        driver.execute_script("arguments[0].click();", radio2)
                    else:
                        print("⚡ Selecting left company...")
                        radio1 = driver.find_element(
                            By.XPATH,
                            "//div[contains(@class, 'modal-dialog')]//div[2]/div/div[1]//input[@type='radio']"
                        )
                        driver.execute_script("arguments[0].click();", radio1)
                    
                    time.sleep(1)
                    
                    # Click the Merge button without confirmation
                    try:
                        merge_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((
                                By.XPATH,
                                "//div[contains(@class, 'modal-dialog')]//footer//button[1]"
                            ))
                        )
                        print("🔄 Merging...")
                        driver.execute_script("arguments[0].click();", merge_button)
                    except Exception as e:
                        try:
                            merge_button = driver.find_element(
                                By.CSS_SELECTOR,
                                "button[data-test-id='merge-modal-lib_merge-button']"
                            )
                            driver.execute_script("arguments[0].click();", merge_button)
                        except Exception as e:
                            raise Exception("Failed to click merge button")
                    
                    print("✅ Merge completed")
                    time.sleep(3)  # Wait for merge to complete
                    print("-" * 70 + "\n")
                    
                except Exception as e:
                    print(f"Error finding contact numbers: {str(e)}")
                    proceed = input("Would you like to continue with the next pair? (y/n): ")
                    if proceed.lower() != 'y':
                        return False
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
        driver.get("REPLACE WITH YOUR HUBSPOT DUPLICATES PAGE URL")
        
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