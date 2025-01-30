# Contact Merge Automation Logic

# 1. First Check: Contact Type
# - Get Contact Type property for both contacts
# - If BOTH contacts are NOT "Company Employee":
#   - Click Cancel button
#   - Click Reject button for the row
#   - Move to next pair
# - If at least one is "Company Employee", continue to email evaluation

# 2. Email Domain Evaluation
# List of free email domains to check against
# - gmail.com
# - outlook.com
# - yahoo.com
# - hotmail.com
# - aol.com
# - icloud.com
# - protonmail.com
# - mail.com
# - zoho.com
# etc...

# Email Comparison Logic:
# a. Check if both contacts have emails
#    - If only one has email, select that contact as primary
#    - If neither has email, move to phone number comparison
#    - If both have emails, continue to domain comparison

# b. Domain Comparison
#    - Extract domain from each email
#    - Check if domains are in free email list
#    - If one email is business (not free) and other is free:
#      -> Select contact with business email
#    - If both are business emails:
#      -> Compare domain extensions using priority list:
#         .com (highest)
#         .io
#         .ai
#         .net
#         .org
#         .co
#         .tech
#         .biz (lowest)
#         others
#      -> Select contact with higher priority domain extension

# 3. Phone Number Comparison (only if no emails or equal email priority)
# - Check if either contact has a phone number
# - If only one has phone number, select that contact
# - If both or neither have phone numbers, keep left contact as default

# 4. Merge Execution
# - Click on the selected contact (left or right)
# - Click Merge button
# - Wait for merge completion
# - Move to next pair

# 5. Error Handling
# - Handle cases where properties are not found
# - Handle cases where buttons are not clickable
# - Handle network issues
# - Log errors and decisions for review 