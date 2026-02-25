#!/usr/bin/env python3
r"""
Standalone script for sending assessment reminders.
Can be run via cron job (Unix/Linux/Mac) or Task Scheduler (Windows).

Usage:
    python send_reminders.py

Setup instructions:
    
    WINDOWS TASK SCHEDULER:
    1. Open Task Scheduler
    2. Create Basic Task → "Send Assessment Reminders"
    3. Trigger: Daily at 09:00
    4. Action: Run program
       - Program: python.exe (full path)
       - Arguments: send_reminders.py
       - Start in: C:\Users\ybassman\Documents\EnrollmentOS
    5. Conditions: Only if network available
    6. Settings: Allow task to run on demand, run task as soon as possible if missed
    
    WINDOWS CRON ALTERNATIVE (using schedule library):
    - Install: pip install schedule
    - Modify this script to run continuously
    
    UNIX/LINUX/MAC CRON:
    1. Run: crontab -e
    2. Add line (to run at 9am every 2 business days):
       0 9 * * 1,3,5 cd ~/Documents/EnrollmentOS && python send_reminders.py >> logs/reminders.log 2>&1
    
    MAC LAUNCHD ALTERNATIVE:
    - See setup_launchd.plist for native approach
"""

import sys
import os
from datetime import datetime

# Add workspace to path
sys.path.insert(0, os.path.dirname(__file__))

import email_reminders


def main():
    """Run the reminder batch."""
    print("\n" + "="*60)
    print("Assessment Reminder Batch Run")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    result = email_reminders.send_reminder_batch()
    
    print("\n" + "="*60)
    print("Summary:")
    print(f"  Reminders sent: {result.get('sent', 0)}")
    print(f"  Skipped (already reminded): {result.get('skipped', 0)}")
    print(f"  Total pending: {result.get('pending_total', 0)}")
    
    if result.get("errors"):
        print("\nErrors:")
        for error in result["errors"]:
            print(f"   - {error}")
    
    print("\n" + "="*60 + "\n")
    
    return 0 if result.get("sent", 0) >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
