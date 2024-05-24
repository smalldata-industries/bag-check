
# Bag Check

Hello! This tool helps you automate fixity checks of collections of files stored in the BagIt format, ensuring the integrity of your files. Follow the instructions below to get started.

## Table of Contents
1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Setup](#setup)
4. [Usage](#usage)
5. [Email Notifications](#email-notifications)
6. [Advanced Usage](#advanced-usage)
7. [Troubleshooting](#troubleshooting)

## Introduction

This tool is provided as-is, with no guarantees or warranties. It is a very basic script intended as a starting point for automating fixity checks, but has not been tested at large scale. Please use this script in a tightly controlled environment, as it includes an unsecured fixity check database and hard-coded email credentials (if you choose to utilize the email functionality)

## Prerequisites

Make sure you have the following installed on your system:
- Python 3
If you are on a Mac this is pre-installed on your system.

## Setup

1. **Clone or download this repository** to your local machine.
2. **Navigate to the directory** where you saved the script.

## Usage

To run the script, open your terminal and navigate to the directory where the script is located. Use the following command:

```bash
/path/to/your/repo/venv/bin/python /path/to/your/repo/bag-checker.py -i /path/to/your/directory -d [recursion depth]
```

Replace `/path/to/your/repo` with the path to your cloned repository, `/path/to/your/directory` with the absolute path to the root directory you want to scan, and `[recursion depth]` with the desired level of recursion for finding bags. For example if you store your materials like this:

```
Root folder
    Artwork 1
        Bag 1
        Bag 2
        Bag 3
    Artwork 2
        Bag 1
    Artwork 3
        Bag 1
        Bag 2
```

Then you would specify `-d 2` when running the script as this tells Bag Check that your bags are always two folders deep. Whereas if your storage looks like this:

```
Root folder
    Bag 1
    Bag 2
    Bag 3
    Bag 4
    Bag 5
    Bag 6
    Bag 7
    Bag 8
    Bag 9
```

Then you would specify `-d 1` since all of the bags are one folder deep in the folder structure.

When you run the script it will look for a previous database file from past fixity checks, and then it will attempt to validate all folders at the depth you specified. The full list of what bags were checked, and their outcome is recorded in the sqlite database named with the timestamp of when the check was run. 

Finally a PDF report is generated that summarizes the high level outcome, and lists the details for any errors that were encountered. If you have email enabled and configured, this PDF will be sent to the specified email address.


## Email Notifications

If you choose to enable email notifications, make sure to fill in the below email settings with your email account details. The script will send a report to the specified recipient and CC addresses after completing the fixity check.

Before running the script, you can adjust the following settings:

- **sendemail**: Set to `True` if you want to send email notifications, otherwise `False`.
- **email settings**: Provide the necessary details for email notifications.

```python
sendemail = False  # Set to True to enable email notifications

# Email settings
email = ''         # The email account to send reports from
password = ''      # Password for the above email account
recipient = ''     # Recipient email address
cc = ''            # CC email address
smtp_server = ''   # SMTP server address
smtp_port = 0      # SMTP server port
```

## Advanced Usage
The script stores data in an SQLite database with two tables: fixityRuns and bags. A new db is created each time the script is run, and it is named with the date and time of the check. Below are examples of how to query this database to extract useful information.

### Example Queries
1. Get All Runs
To retrieve all runs from the fixityRuns table: 
```
SELECT * FROM fixityRuns;
```

2. Get All Bags in a Specific Run
To retrieve all bags checked during a specific run (replace run_number with the actual run number): 
```
SELECT * FROM bags WHERE runid = (SELECT id FROM fixityRuns WHERE run_num = run_number);
```

3. Count of Valid and Invalid Bags
To get the count of valid and invalid bags for each run:
```
SELECT run_num, 
       SUM(CASE WHEN validation_outcome = 'Valid' THEN 1 ELSE 0 END) AS valid_count,
       SUM(CASE WHEN validation_outcome = 'Invalid' THEN 1 ELSE 0 END) AS invalid_count
FROM fixityRuns fr
JOIN bags b ON fr.id = b.runid
GROUP BY run_num;
```

4. Bags with Errors
To find all bags that encountered errors during validation:

```
SELECT * FROM bags WHERE BagError IS NOT NULL OR ValidationError IS NOT NULL;
```

5. List of Missing Bags
To list all bags that were marked as missing: 
```
SELECT * FROM bags WHERE validation_outcome = 'Missing';
```

To run these (and more) quries you can use any database browsing application that supports sqlite, or the sqlite command line interface.

## Troubleshooting
I hope this tool can help some of those of you out there. If you have any questions or encounter any issues, feel free to reach out: cass@smalldata.industries
