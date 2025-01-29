# HubSpot Company Merge Automation 🤖

A Python automation script that helps you merge duplicate companies in HubSpot without needing Operations Hub. Save hours of manual work by automating the company merge process.

## Why This Tool? 🎯

- **Save Time**: Automate repetitive company merging tasks
- **No Operations Hub Required**: Get enterprise-level automation without the enterprise price tag
- **Smart Selection**: Automatically picks the best company record based on:
  1. Number of associated contacts
  2. Domain quality (e.g., .com preferred over .net)

## Features ✨

- 🔄 Batch processing of duplicate companies
- 🧠 Smart primary record selection based on:
  - Contact count comparison
  - Domain extension ranking (.com > .io > .ai > .net > .org > .co > .tech > .biz)
- 👤 Chrome profile support (use your existing logged-in session)
- 📊 Clear console output showing comparison and decisions
- ⚡ Fully automated merging with minimal user interaction
- 🔒 Safe and secure (runs locally, no API keys needed)

## Requirements 📋

- Python 3.6+
- Chrome Browser
- macOS (for current version - Windows not supported)

## Installation 🛠️

1. Clone this repository:
```bash
git clone [repository-url]
cd hubspot_deduplicate_automation
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage 🚀

1. Run the script:
```bash
python automation_script.py or python3 automation_script.py
```

2. Select your Chrome profile when prompted

3. Log into HubSpot in the opened browser (if needed)

4. Enter the number of duplicate pairs you want to process

5. Watch the magic happen! The script will:
   - Compare duplicate companies
   - Select the best primary record
   - Merge automatically
   - Show you what's happening at each step

## How It Works 🔍

The script uses the following logic to determine which company record should be the primary record:

1. **Contact Count**: Company with more associated contacts becomes primary
2. **Domain Preference**: If contact counts are equal, uses domain ranking:
   - .com (highest priority)
   - .io
   - .ai
   - .net
   - .org
   - .co
   - .tech
   - .biz (lowest priority)
   - Other domains default to keeping left company

## Safety Features 🛡️

- Uses your existing Chrome profile for authentication
- No stored credentials
- Runs locally on your machine
- Ability to stop at any time
- Option to keep browser open for verification

## Limitations ⚠️

- Currently supports macOS only
- Requires Chrome browser
- Must have access to HubSpot's duplicate management tool
- Maximum of 50 pairs per batch (HubSpot limitation)

## Contributing 🤝

Feel free to:
- Open issues
- Submit pull requests
- Suggest improvements
- Report bugs

## License 📄

MIT License - feel free to use and modify as needed!

## Future Work 🚀

### Improvements

1. **Enhanced Batch Processing**
   - Implement pagination to handle more than 50 merges at a time
   - Auto-navigate through multiple pages of duplicates
   - Track progress across pages
   - Resume capability for interrupted batch processes

2. **Smarter Domain Comparison**
   - Add more domain extensions to the ranking system:
     - Country-specific domains (.us, .uk, .ca, etc.)
     - Industry-specific domains (.app, .dev, .cloud, etc.)
     - Regional domains (.eu, .asia, etc.)
   - Custom domain ranking configuration
   - Domain age consideration in ranking

3. **Better Error Handling**
   - Handle already-merged company scenarios
   - Detect and skip companies without domains
   - Handle duplicate entries in multiple merge pairs
   - Logging system for failed merges
   - Retry mechanism for failed merges

4. **Additional Features**
   - Windows OS support
   - Command-line arguments for batch size and other options
   - Progress saving and restoration
   - Detailed merge reports and statistics
   - Custom merge rules configuration

### Known Issues to Address
- Companies without domains appearing in multiple merge pairs
- Merge failures when company was already merged in previous pair
- 50-pair batch limitation from HubSpot's interface

Feel free to contribute to any of these improvements!

## Disclaimer ⚖️

This tool is not officially affiliated with HubSpot. Use at your own discretion and always verify the results. 