import datetime


def get_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def get_date_12hr_min():
    return datetime.datetime.now().strftime("%Y-%m-%d: %I:%M%p")

def get_date_24hr_min():
    return datetime.datetime.now().strftime("%Y-%m-%d: %H:%M")