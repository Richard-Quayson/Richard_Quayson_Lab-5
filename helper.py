import json
from decimal import Decimal
from datetime import timedelta
from pytz import timezone
from flask import jsonify
from firebase_admin import credentials, firestore, initialize_app


# Initialising Firestore db
cred = credentials.Certificate("key.json")
default_app = initialize_app(cred)
database = firestore.client()

# the first year group for Ashesi University
FIRST_YEAR_GROUP = 2002

VOTERS_COLLECTION = database.collection("voters")
ELECTIONS_COLLECTION = database.collection("elections")


def valid_request_body(request):
    """ensures that the request body is valid (not empty)

    Args:
        request (tuple): the request being sent to the API

    Returns:
        JSON: a boolean of whether or not the request is valid
    """
    
    if not request.data:
        return False    
    return True


def valid_keys(voter_info, expected_keys):
    """validates a voter's information and returns result

    Args:
        voter_info (dict): JSON representation of a voter's information

    Returns:
        dict: a dictionary of boolean and or list of messages from validation
    """
    
    result = {"is_valid": False}            # result from validation
    result_message = []                     # message from validation
    num_correct_keys = 0                    # variable to keep track of the number of matching keys
    data_keys = voter_info.keys()
    
    for key in expected_keys:
        if key in data_keys:
            num_correct_keys += 1
        else:
            result_message.append(f"{key.capitalize()} is required")
    
    if num_correct_keys == len(expected_keys):
        result["is_valid"] = True
    else:
        result["message"] = result_message
    
    return result


def key_is_unique(key_list, dictionary_list, voter_info):
    """ensures that all values corresponding to unique keys in the provided 
    voter information is unique (does not already exist in voters file)

    Args:
        key_list (list): list of unique keys
        dictionary_list (list of dict): a list of voter information (dict)
        voter_info (dict): a dictionary containing voter information

    Returns:
        result: a dictionary containing the result from unique test
    """
    
    result = dict()
    for key in key_list:
        for voter in dictionary_list:        
            if voter_info[key] == voter[key] and voter["student_id"] != voter_info["student_id"]:
                result[key] = key + " already exists!"
    
    return result


def valid_student_id(student_id):
    """ensures that a given student_id is valid
    - a student ID is valid if it's eight characters long and numeric

    Args:
        student_id (str): a student's ID

    Returns:
        dict: a dictionary containing user_id (the first four values of a student id)
        and year_group (the year group of the student)
    """
    
    # ensure that the student id is of length 8
    if(len(student_id)) != 8:
        return False
    
    # ensure that the student id is numeric
    if not student_id.isnumeric():
        return False
    
    user_id = student_id[:4]
    year_group = student_id[4:]
    
    return {"user_id": user_id, "year_group": year_group} 


def valid_voter_info(request, unique_keys):
    """ensures that a voter request data is valid
    i.e. contains all necessary keys, contains unique values for
    unique keys, student_id, firstname, lastname and email are syntactically valid

    Args:
        request (tuple): request from client
        unique_keys (list): a list of keys that should be unique

    Returns:
        dict: dictionary containing the status of the validation 
        and a JSON representation of the voter's info from the request or
        appropriate message if an exception occurred
    """
    
    # ensure that the voter_info is not empty
    if not valid_request_body(request):
        return jsonify({"message": "Voter information missing!"}), 400
    
    # get request data
    voter_info = json.loads(request.data)
    
    # ensure that the data contains all expected fields
    # if validation fails, return appropriate message
    # expected keys
    VOTERS_KEYS = [
            "student_id", "firstname", "lastname", "email"
        ]
    
    validate_data = valid_keys(voter_info, VOTERS_KEYS)
    if validate_data["is_valid"] == False:
        return jsonify(validate_data["message"]), 400
    
    # ensure that the student_id is synctactically correct since
    # the system assumes a certain format for later computation
    student_id_is_valid = valid_student_id(voter_info["student_id"])
    if not student_id_is_valid:
        return jsonify({"message": "Student ID is not valid."}), 400
    elif int(student_id_is_valid["year_group"]) < FIRST_YEAR_GROUP:
        return jsonify({"message": "Student year group is invalid."})
    
    # ensure that the email is a valid ashesi email
    if not voter_info["email"].endswith("@ashesi.edu.gh"):
        return jsonify({"message": "Email must be a valid Ashesi email address."}), 400
    
    # ensure that firstname and lastname is valid (is a string)
    if not str(voter_info["firstname"]).isalpha() or not str(voter_info["lastname"]).isalpha():
        return jsonify({"message": "Firstname or Lastname must be a string."}), 400
    
    # reading existing data into a list
    voters_data = VOTERS_COLLECTION.get()
    
    # if no voter has been registered, skip unique test
    if len(voters_data) == 0:
        return {"data": voter_info}
    
    # ensure keys are unique
    # if unique contraints fails, return appropriate response
    data_list = list()
    for document in voters_data:
        data_list.append(document.to_dict())
    
    ununique_result = key_is_unique(unique_keys, data_list, voter_info)
    if len(ununique_result) > 0:
        return jsonify(ununique_result), 400
    
    return {"data": voter_info}


def get_voters(id_list):
    
    result_list = list()
    return_data = dict()
    # read voters database
    voters_data = VOTERS_COLLECTION.get()
    
    if not voters_data:
        return {"message": "No voter has been registered!"}
    
    for voter in voters_data:
        voter = voter.to_dict()
        if voter["student_id"] in id_list and bool(voter["is_registered"]) == True:
            result_list.append(voter)
            if len(result_list) == len(id_list):
                return return_data

    return False


def compute_time(time_period):
    num_days = int(int(time_period) / 24)
    num_hours = 0
    num_minutes = 0

    if time_period % 24 != 0:
        hours = time_period - (num_days * 24)
        num_hours = int(hours)
        
        if isinstance(hours, Decimal):
            hour_decimal = Decimal(str(hours)) % 1
            num_minutes = int(60 * hour_decimal)
    return num_days, num_hours, num_minutes


def get_duration(election):
    num_days, num_hours, num_minutes = compute_time(election["election_period"])
    duration = timedelta(days=num_days, hours=num_hours, minutes=num_minutes)
    return str(duration)
    
    
def get_end_date(election):
    num_days, num_hours, num_minutes = compute_time(election["election_period"])
    time_change = timedelta(days=num_days, hours=num_hours, minutes=num_minutes)
    return election["election_startdate"] + time_change


def get_remaining_time(election):
    zone_name = "Africa/Accra"
    current_time = timezone(zone_name)
    return str(election["election_end_date"] - current_time)