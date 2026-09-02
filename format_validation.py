from datetime import datetime

def validate_date(date_str, date_type):
    try:
        # format validation
        if datetime.strptime(date_str, '%Y-%m-%d') > datetime.now():
            print(f'Error: {date_type} cannot be in the future.')
            return False
        return True
    except ValueError:
        print(f'Error: {date_type} must be in YYYY-MM-DD format.')
        return False