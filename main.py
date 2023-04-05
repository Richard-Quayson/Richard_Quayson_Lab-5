# import necessary libraries
import os
import json
# import functions_framework
from datetime import timedelta
from flask import Flask, jsonify

# import helper methods
from helper import (
    valid_request_body, valid_voter_info, 
    valid_student_id, valid_keys,
    key_is_unique, get_voters,
    
    FIRST_YEAR_GROUP, VOTERS_COLLECTION, 
    ELECTIONS_COLLECTION
)


# Initialising the flask app
voting_app = Flask(__name__)


# flask app to handle all requests in the API
# @functions_framework.http
voting_app.route("/", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
def voting_system(request):
    if "voters" in request.path:
        if request.method == "POST":
            return register_voter(request)
        elif request.method == "PATCH":
            return deregister_voter(request)
        elif request.method == "GET":
            return get_voters(request)
        elif request.method == "PUT":
            return update_voter(request)

    elif "elections" in request.path:
        if request.method == "POST":
            return create_election(request)
        elif request.method == "GET":
            return retrieve_election(request)
        elif request.method == "DELETE":
            return delete_election(request)
        elif request.method == "POST" and "vote" in request.path:
            return vote(request)

    else:
        return jsonify({"message": "Invalid endpoint!"}), 404
    

# _____________________________________________________________________________________________________________________
# REGISTER AN ASHESI STUDENT AS A VOTER
# @voting_app.route("/voters/register_voter/", methods=["POST"])
def register_voter(request):
    """handles a POST request to created a voter and returns a JSON
    object of the voter's information if all validation and constraints
    are met. Else, returns JSON representation of the validation or constraint failure

    Returns:
        JSON: an appropriate JSON of voter information or exception encountered
    """
    
    # ensure that the voter_info is not empty
    if not valid_request_body(request):
        return jsonify({"message": "Voter information missing!"}), 400
    
    # validate voter info for unique constraints and input validation
    unique_keys = ["student_id", "email"]
    response = valid_voter_info(request, unique_keys)
    if type(response) == tuple:
        return response
    
    voter_info = response["data"]
    # set can vote attribute
    voter_info["is_registered"] = True
    
    # write the data into the voters collection
    VOTERS_COLLECTION.document(voter_info["student_id"]).set(voter_info)
        
    return jsonify(voter_info), 201


# __________________________________________________________________________________________________________________________
# DEREGISTER A STUDENT AS A VOTER
# @voting_app.route("/voters/de_register/<value>/", methods=["PATCH"])
def deregister_voter(request):
    """deregisters a specified voter (voter with given student id) or 
    specified voters (students in a particular year group) by setting their
    is_registered attribute to false

    Args:
        value (str): year group or student id of student(s) to be deregistered

    Returns:
        JSON: JSON representation of students deregistered or appropriate message
        if an exception occurs
    """
    if request.data.get("student_id"):
        value = request.data.get("student_id")
        print(value)
    elif request.data.get("year_group"):
        value = request.data.get("year_group")
    else:
        return jsonify({"message": "Invalid attribute!"}), 400
    
    # check if the value parsed is a year group
    # else, assume it is a student id
    if len(value) == 4 and value.isnumeric() and int(value) >= FIRST_YEAR_GROUP:
        key = "year_group"
    else:
        key = "student_id"
        # ensure that the student id is valid
        if not valid_student_id(value):
            return jsonify({"message": "Invalid student id!"}), 400
    
    voters_data = VOTERS_COLLECTION.get()              # get all voters    
    updated_voters_data = list()                    # list of all voters
    updated_voters = []                             # list of only updated voters

    # update specified user's is_registered attribute to deregister them
    if key == "student_id":
        for voter in voters_data:
            voter = voter.to_dict()
            if voter[key] == value:
                voter["is_registered"] = False
                updated_voters.append(voter)
            updated_voters_data.append(voter)
    
    # updated all students in specified year group's is_registered attribute
    else:
        for voter in voters_data:
            voter = voter.to_dict()
            id_details = valid_student_id(voter["student_id"])
            if id_details[key] == value:
                voter["is_registered"] = False
                updated_voters.append(voter)
            updated_voters_data.append(voter)
        
    # if user with id not found, return appropriate message
    if not updated_voters and key == "student_id":
        return jsonify({"message": f"student with id {value} has not been registered as a voter!"}), 404
    elif not updated_voters and key == "year_group":
        return jsonify({"message": f"No registered voter in the {value} year group!"}), 404    
        
    # write updated data into the voters collection
    for voter in updated_voters:
        VOTERS_COLLECTION.document(voter["student_id"]).set(voter)

    # attach appropriate message title
    if key == "student_id":
        updated_voters.insert(0, {"message": f"Student with id {value} has been de-registered!"})
    else:
        updated_voters.insert(0, {"message": f"Users in year group {value} have been de-registered!"})
    
    return jsonify(updated_voters)


# ____________________________________________________________________________________________________________________________________
# UPDATE REGISTERED VOTER'S INFORMATION
# @voting_app.route("/voters/update_voter/<student_id>/", methods=["PUT"])
def update_voter(request):
    """updates the details of the voter with the specified student id if it exists
    else it creates a new record in the database if the request data meet all specified constraints

    Args:
        student_id (str): the voter's student id

    Returns:
        dict: JSON object of the updated or created object
    """
    if request.data.get("student_id"):
        student_id = request.data.get("student_id")
    else:
        return jsonify({"message": "Invalid attribute!"}), 400
    
    # ensure that the student id is valid
    if not valid_student_id(student_id):
        return jsonify({"message": "Invalid student id!"}), 400
    
    unique_keys = ["email"]
    # validate voter_info
    response = valid_voter_info(request, unique_keys)
    # if validation failed, return appropriate message
    if type(response) == tuple:         
        return response
    
    # get validated voter info 
    voter_info = response["data"]
    
    if not voter_info["is_registered"]:
        return jsonify({"message": "You cannot use update to deregister, use dregister function instead!"})
    
    # reading existing data into a list
    voters_data = VOTERS_COLLECTION.get()
    updated_voters_data = list()
 
    if not voters_data:
        VOTERS_COLLECTION.document(voter_info["student_id"]).set(voter_info)
    else:
        # get the voter with specified id
        for voter in voters_data:
            voter = voter.to_dict()
            if voter["student_id"] == voter_info["student_id"]:

                # ensure that the voter specified is registered
                if not voter["is_registered"]:
                    return jsonify({"message": f"Voter with id {student_id} is not registered."}), 404
                
                # replace data in file
                voter = voter_info
                voter["is_registered"] = True
            updated_voters_data.append(voter)
        
    # write the updated data into the file
    for voter in updated_voters_data:
        VOTERS_COLLECTION.document(voter["student_id"]).set(voter)
    
    return jsonify(voter_info)


# ________________________________________________________________________________________________________________________________________________
# RETRIEVE A REGISTERED VOTER 
# @voting_app.route("/voters/get/", methods=["GET"])
def retrieve_voters(request):
    """uses all specified arguments (attributes of voter) parsed for filtering
    matching voters and returns the result. If no attribute is parsed, it retrieves
    all users If any exception occur, it returns an appropriate message of the exception
    * Attributes being used for filtering are: 
    - student_id           - firstname
    - lastname              - email         - year_group

    Returns:
        dict: JSON representation of the list of voters (dict) that match filter attributes
    """
    
    # dict to store all keys and values for filter
    filter_dict = dict()
    
    # stores resulting list from filtering
    result_list = list()
    final_result_list = list()
    
    # get all attributes specified in the request args
    if request.args.get("student_id"):
        filter_dict["student_id"] = request.args.get("student_id")
        
    if request.args.get("firstname"):
        filter_dict["firstname"] = request.args.get("firstname")
        
    if request.args.get("lastname"):
        filter_dict["lastname"] = request.args.get("lastname")
        
    if request.args.get("email"):
        filter_dict["email"] = request.args.get("email")
        
    if request.args.get("year_group"):
        filter_dict["year_group"] = request.args.get("year_group")
        
    if request.args.get("is_registered"):
        filter_dict["is_registered"] = request.args.get("is_registered")

    # read the voters file
    data = VOTERS_COLLECTION.get()
    voters_data = list()
    for voter in data:
        voters_data.append(voter.to_dict())
        
    if not voters_data:
        return jsonify({"message": "No voter has been registered!"}), 404
    
    # if no argument is parsed, retrieve all users
    if not filter_dict:
        return jsonify(voters_data)
        
    for key in filter_dict.keys():

        # ensure that the value of key is valid
        if key == "student_id":
            student_id_is_valid = valid_student_id(filter_dict[key])
            if not student_id_is_valid:
                return jsonify({"message": "Student ID is not valid."}), 400

        elif key == "firstname":
            if not str(filter_dict[key]).isalpha():
                return jsonify({"message": "Firstname must be a string."}), 400
            
        elif key == "lastname":
            if not str(filter_dict[key]).isalpha():
                return jsonify({"message": "Lastname must be a string."}), 400
        
        elif key == "email":
            if not filter_dict[key].endswith("@ashesi.edu.gh"):
                return jsonify({"message": "Email must be a valid Ashesi email address."}), 400
            
        elif key == "is_registered":
            if filter_dict[key].lower() == "true":
                filter_dict[key] = True
            elif filter_dict[key].lower() == "false":
                filter_dict[key] = False
            else:
                return jsonify({"message": "Invalid value for is_registered attribute!"}), 400
            
        else:
            if int(filter_dict["year_group"]) < FIRST_YEAR_GROUP:
                return jsonify({"message": "Student year group is invalid."})
            
        # empty the result list before new filter is applied
        result_list.clear()
            
        # get all user with specified key
        for voter in voters_data:
            # since year group isn't being stored, handle it differently
            if key == "year_group":
                # get year group of voter from voter's student_id
                student_id_details = valid_student_id(voter.get("student_id"))
                year_group = student_id_details["year_group"]
                if year_group == filter_dict[key]:
                    result_list.append(voter)
            else:
                if type(filter_dict[key]) == str:
                    if voter.get(key).lower() == filter_dict[key].lower() or voter.get(key).lower().startswith(filter_dict[key].lower()):
                        result_list.append(voter)
                else:
                    if voter.get(key) == filter_dict[key]:
                        result_list.append(voter)
        
        # update the data being returned
        final_result_list = result_list[:]
        
        # update the data being used for filtering
        voters_data = final_result_list
                
    # ensure that the result list is not empty
    if not final_result_list:
        return jsonify({"message": "No voter found with the provided details"}), 404
            
    return jsonify(final_result_list)


# ______________________________________________________________________________________________________________________________________________________________
# CREATE AN ELECTION
# @voting_app.route("/elections/create_election/", methods=["POST"])
def create_election(request):
    
    # ensure that the request's data is not empty
    if not valid_request_body(request):
        return jsonify({"message": "Election information not provided!"}), 404
    
    # get election information from request 
    election_info = json.loads(request.data)
    
    # ensure that the data contains all expected fields
    # if validation fails, return appropriate message
    # expected keys
    ELECTION_KEYS = [
            "election_code", "election_name", "election_startdate",
            "election_period", "positions"
        ]
    
    validate_data = valid_keys(election_info, ELECTION_KEYS)
    if validate_data["is_valid"] == False:
        return jsonify(validate_data["message"]), 400
    
    # read existing elections data
    data = ELECTIONS_COLLECTION.get()
    
    # validate election unique constraints if there are existing election information
    unique_keys = ["election_code", "election_name"]
    if data:    
        elections_data = json.loads(data)
        ununique_result = key_is_unique(unique_keys, elections_data, election_info)
        if len(ununique_result) > 0:
            return jsonify(ununique_result), 400
        
    # NOTE: PROGRAM ASSUMES DATA FOR VARIOUS FIELDS HAVE BEEN VALIDATED AND DATA FORMATS (STRUCTURES, etc) ARE VALID
        
    # EXTRA FIELDS NEEDED IN PROGRAM:
    # 1. add num_votes to all candidates provided for a position 
    # 2. add voters (a list of voters who have voted for a candidate) to all positions
    
    election_positions = election_info["positions"]
    updated_positions = list()
    for position in election_positions:
        updated_candidates = list()
        candidates = position["candidates"]
        
        for candidate in candidates:
            candidates_dictionary = dict()
            candidates_dictionary["candidate_id"] = candidate
            candidates_dictionary["candidate_voters"] = list()
            
            updated_candidates.append(candidates_dictionary)

        position["candidates"] = updated_candidates
        updated_positions.append(position)
    
    election_info["positions"] = updated_positions     
    
    # write the data to elections collection
    ELECTIONS_COLLECTION.document(election_info["election_code"]).set(election_info)
    
    return jsonify(election_info)


# ____________________________________________________________________________________________________________________________________________________
# RETRIEVE AN ELECTION
# @voting_app.route("/elections/get/<election_code>/", methods=["GET"])
def retrieve_election(request):

    # read election file
    elections_data = ELECTIONS_COLLECTION.get()

    # get election code from request
    if request.args.get("election_code") == None:
        return jsonify(elections_data)
    
    election_code = request.args.get("election_code")
    
    # ensure that there are existing data
    if not elections_data:
        return jsonify({"message": "No elections have been created!"}), 404
    
    # loop through data and check if requested key exists
    for election in elections_data:
        election = election.to_dict()
        if election["election_code"] == election_code:
            return jsonify(election)
    
    return jsonify({"message": "Election with requested code does not exist!"}), 404


# _______________________________________________________________________________________________________________________________________________________
# DELETE AN ELECTION
# @voting_app.route("/elections/delete_election/<election_code>/", methods=["DELETE"])
def delete_election(request):
    # read election file
    elections_data = ELECTIONS_COLLECTION.get()

    # get election code from request
    if request.data.get("election_code"):
        election_code = request.data.get("election_code")
    else:
        return jsonify({"message": "Election code not provided!"}), 400
    
    # ensure that there are existing data
    if not elections_data:
        return jsonify({"message": "No elections have been created!"}), 404
        
    # delete document from elections collection
    if ELECTIONS_COLLECTION.document(election_code).delete():
        return jsonify({"message": f"Election with code {election_code} has been deleted successfully!"}) #, 204
    
    return jsonify({"message": "Election with requested code does not exist!"}), 404


# ________________________________________________________________________________________________________________________________________________________
# VOTE IN AN ELECTION
# @voting_app.route("/elections/vote/<election_code>/", methods=["POST"])
def vote(request):
    
    # get position from URL argument
    position_id = request.args.get("position_id")
    
    if not position_id:
        return jsonify({"message": "Missing election position!"}), 400
    
    # ensure that the request body is not empty
    if not valid_request_body(request):
        return jsonify({"message": "Election information not provided!"}), 404
    
    # get request data
    vote_info = json.loads(request.data)

    # get election code from data
    if request.data.get("election_code"):
        election_code = request.data.get("election_code")
    
    # ensure that the data contains student_id and candidate_id
    VOTING_KEYS = [
            "student_id", "candidate_id"
        ]
    
    validate_data = valid_keys(vote_info, VOTING_KEYS)
    if validate_data["is_valid"] == False:
        return jsonify(validate_data["message"]), 400
    
    # ensure that the student id is valid
    student_id_is_valid = valid_student_id(vote_info["student_id"])
    if not student_id_is_valid:
        return jsonify({"message": "Student ID is not valid."}), 400
    
    # ensure that the candidate id is valid
    student_id_is_valid = valid_student_id(vote_info["candidate_id"])
    if not student_id_is_valid:
        return jsonify({"message": "Candidate ID is not valid."}), 400
    
    # ensure that the student and the candidate are both registered
    student_list = [vote_info["student_id"], vote_info["candidate_id"]]
    students_registered = get_voters(student_list)
    
    if students_registered == False:
        return jsonify({"message": "Voter or candidate not registered!"}), 404
    
    # read data
    voters_data = VOTERS_COLLECTION.get()
    elections_data = ELECTIONS_COLLECTION.get()
    
    if not voters_data:
        return jsonify({"message": "No voter has been registered!"}), 404
    
    if not elections_data:
        return jsonify({"message": "No election has been created!"}), 404
    
    election_info = None
    updated_elections_data = list()
    
    for election in elections_data:
        election = election.to_dict()
        if election["election_code"] == election_code:
            
            # ensure that the position exist
            positions = election["positions"]
            updated_position = list()
            for position in positions:
                if position["position_id"] == position_id:
                    
                    all_voters = list()
                    # ensure that the candidate is valid
                    candidate_exists = False
                    candidates = position["candidates"]
                    updated_candidate = list()
                    for candidate in candidates:
                        # get all those who have voted in that election position
                        all_voters.extend(candidate["candidate_voters"])
                        
                        if candidate["candidate_id"] == vote_info["candidate_id"]:
                            candidate_exists = True
                            
                    if not candidate_exists:
                        return jsonify({"message": f"Candidate with id {vote_info['candidate_id']} has not been registered for the {position['position_name']} position!"})
                    
                    # ensure that the candidate hasn't voted before
                    if vote_info["student_id"] in all_voters:
                        return jsonify({"message": "You cannot vote twice for one position!"}), 403
                    
                    # cast vote by adding student id to candidate_voters
                    for candidate in candidates:
                        if candidate["candidate_id"] == vote_info["candidate_id"]:
                            candidate["candidate_voters"].append(vote_info["student_id"])
                            
                        updated_candidate.append(candidate)
                    position["candidates"] = updated_candidate
                    
                    break
                updated_position.append(position)
            election_info = election
            updated_elections_data.append(election)

            break
        updated_elections_data.append(election)
    
    if election_info == None:
        return jsonify({"message": f"Election with code {election_code} does not exist!"}), 404
    
    # write result to the elections collection
    for election in updated_elections_data:
        ELECTIONS_COLLECTION.document(election["election_code"]).set(election)
        
    return jsonify(election_info)

# if __name__=='__main__':
#     voting_app.run()