# HubSpot Duplicate Company Automation

Automates the process of merging or rejecting duplicate companies in HubSpot.

## Features

- Automated duplicate company processing
- **Unlimited batch processing** - no 50-pair limit
- Dynamic row processing as pairs are merged/rejected
- Smart handling of merge errors and conflicts
- Efficient tracking of already processed companies
- Performance optimized with minimal wait times
- Reliable error recovery and state management
- Support for multiple Chrome profiles
- Manual login support for security
- Progress tracking and statistics

## Performance Optimizations

- Minimal wait times (0.3-1.5s) for maximum efficiency
- Pre-compiled XPath expressions
- Efficient element finding strategies
- Smart page load detection
- Combined JavaScript operations
- Explicit waits instead of sleep timers
- Dynamic row detection and processing

## Requirements

- Python 3.7+
- Chrome browser
- macOS (currently optimized for)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/hubspot_deduplicate_automation.git
cd hubspot_deduplicate_automation
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the script:
```bash
python automation_script.py
```

2. Select your Chrome profile when prompted

3. Log in to HubSpot manually when the browser opens

4. Enter the number of duplicate pairs you want to process
   - No limit on number of pairs
   - Script will dynamically process new rows as they appear
   - Progress updates every 10 pairs

The script will automatically:
- Process the specified number of pairs
- Handle merge errors gracefully
- Track already processed companies
- Show progress and remaining pairs
- Allow you to process multiple batches

## Progress Tracking

The script now provides:
- Current pair number being processed
- Total pairs processed so far
- Number of pairs remaining visible
- Progress updates every 10 pairs
- Completion statistics

## Error Handling

The script handles several scenarios:
- Already merged companies
- Unmergeable companies
- Network issues
- Page load failures
- Element interaction failures
- Dynamic row updates

## Configuration

No configuration needed - the script automatically:
- Detects Chrome profiles
- Handles login security
- Manages browser state
- Tracks processed companies
- Handles dynamic content updates

## Notes

- The script uses JavaScript execution for better performance
- Wait times are optimized but can be adjusted if needed
- Error recovery is automatic in most cases
- Manual intervention is requested only when necessary
- No artificial limits on batch size

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
- Merge failures when company was previously merged (now tracked and rejected)

Feel free to contribute to any of these improvements!

## Disclaimer ⚖️

This tool is not officially affiliated with HubSpot. Use at your own discretion and always verify the results. 