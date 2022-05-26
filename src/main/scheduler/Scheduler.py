from model.Vaccine import Vaccine
from model.Caregiver import Caregiver
from model.Patient import Patient
from util.Util import Util
from db.ConnectionManager import ConnectionManager
import pymssql
import datetime


'''
objects to keep track of the currently logged-in user
Note: it is always true that at most one of currentCaregiver and currentPatient is not null
        since only one user can be logged-in at a time
'''
current_patient = None

current_caregiver = None

'''
Helper Functions
'''


def username_exists(username, role):
    cm = ConnectionManager()
    conn = cm.create_connection()

    select_username = "SELECT * FROM " + role + " WHERE Username = %s"
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(select_username, username)
        #  returns false if the cursor is not before the first record or if there are no rows in the ResultSet.
        for row in cursor:
            return row['Username'] is not None
    except pymssql.Error as e:
        print("Error occurred when checking username")
        print("Db-Error:", e)
        quit()
    except Exception as e:
        print("Error occurred when checking username")
        print("Error:", e)
    finally:
        cm.close_connection()
    return False


def print_availability(date):
    cm = ConnectionManager()
    conn = cm.create_connection()
    cursor = conn.cursor()

    availability = "SELECT Username FROM Availabilities WHERE Time = %s ORDER BY Username ASC"
    get_vaccine = "SELECT Name, Doses FROM Vaccines"
    try:
        cursor.execute(get_vaccine)
        doses = " "
        print("Caregiver", end = " ")
        for row in cursor:
            print(str(row[0]), end = " ")
            doses += str(row[1]) + " "
        print()
        cursor.execute(availability, date)
        for row in cursor:
            print(str(row[0]) + doses)

    except pymssql.Error as e:
        raise e
    finally:
        cm.close_connection()


def get_available_caregiver(date):
    cm = ConnectionManager()
    conn = cm.create_connection()
    cursor = conn.cursor()

    availability = "SELECT Top 1 Username FROM Availabilities WHERE Time = %s ORDER BY Username ASC"
    try:
        cursor.execute(availability, date)
        if (cursor.rowcount == 0):
            return None

        for row in cursor:
            return str(row[0])

    except pymssql.Error as e:
        print(e)
        raise e
    finally:
        cm.close_connection()

def create_appointment(date, caregiver, vaccine, patient):
    cm = ConnectionManager()
    conn = cm.create_connection()
    cursor = conn.cursor()

    delete_availability = "DELETE FROM Availabilities WHERE Username = %s AND Time = %s"
    update_vaccine_availability = "UPDATE vaccines SET Doses = %d WHERE name = %s"
    insert_appointment = """
        DECLARE @temp TABLE (Id int, Caregiver VARCHAR(255))
        INSERT INTO Appointments OUTPUT Inserted.ID, Inserted.Caregiver INTO @temp VALUES (%s, %s, %s, %s)
        SELECT * FROM @temp
    """

    try:
        cursor.execute(
            delete_availability,
            (caregiver, date)
        )
        cursor.execute(
            update_vaccine_availability,
            (vaccine.get_available_doses() - 1, vaccine.get_vaccine_name())
        )
        cursor.execute(
            insert_appointment,
            (date, caregiver, vaccine.get_vaccine_name(), patient)
        )
        for row in cursor:
            print("Appointment ID: " + str(row[0]) + " Caregiver username: " + str(row[1]))
        conn.commit()

    except Exception as E:
        print(str(E))
        raise E
    finally:
        cm.close_connection()


def delete_appointment(Id):
    cm = ConnectionManager()
    conn = cm.create_connection()
    cursor = conn.cursor()

    delete_appointment = """
        DECLARE @temp TABLE (Time date, Caregiver VARCHAR(255), Vaccine VARCHAR(255))
        DELETE FROM Appointments OUTPUT Deleted.Time, Deleted.Caregiver, Deleted.Vaccine INTO @temp WHERE Id = %s
        SELECT * FROM @temp
    """
    insert_availability = "INSERT INTO Availabilities VALUES (%s, %s)"
    get_vaccine_doses = "SELECT Doses FROM Vaccines WHERE name = %s"
    update_vaccine_availability = "UPDATE vaccines SET Doses = %d WHERE name = %s"

    try:
        cursor.execute(delete_appointment, Id)
        deleted = cursor.fetchall()
        for row in deleted:
            cursor.execute(insert_availability, (str(row[0]), str(row[1])))
            cursor.execute(get_vaccine_doses, str(row[2]))
            dose = cursor.fetchall()
            for inner_row in dose:
                cursor.execute(update_vaccine_availability, (inner_row[0], str(row[2])))

        conn.commit()

    except Exception as E:
        print(str(E))
        raise E
    finally:
        cm.close_connection()


'''
Command Functions
'''

def create_patient(tokens):
    # create_patient <username> <password>
    # check 1: the length for tokens need to be exactly 3 to include all information (with the operation name)
    if len(tokens) != 3:
        print("Failed to create user.")
        return

    username = tokens[1]
    password = tokens[2]
    # check 2: check if the username has been taken already
    if username_exists(username, "Patients"):
        print("Username taken, try again!")
        return

    if (not Util.strong_password(tokens[2])):
        return

    salt = Util.generate_salt()
    hash = Util.generate_hash(password, salt)

    # create the caregiver
    patient = Patient(username, salt=salt, hash=hash)

    # save to caregiver information to our database
    try:
        patient.save_to_db()
    except pymssql.Error as e:
        print("Failed to create user.")
        print("Db-Error:", e)
        quit()
    except Exception as e:
        print("Failed to create user.")
        print(e)
        return
    print("Created user ", username)


def create_caregiver(tokens):
    # create_caregiver <username> <password>
    # check 1: the length for tokens need to be exactly 3 to include all information (with the operation name)
    if len(tokens) != 3:
        print("Failed to create user.")
        return

    username = tokens[1]
    password = tokens[2]
    # check 2: check if the username has been taken already
    if username_exists(username, "Caregivers"):
        print("Username taken, try again!")
        return

    if (not Util.strong_password(tokens[2])):
        return

    salt = Util.generate_salt()
    hash = Util.generate_hash(password, salt)

    # create the caregiver
    caregiver = Caregiver(username, salt=salt, hash=hash)

    # save to caregiver information to our database
    try:
        caregiver.save_to_db()
    except pymssql.Error as e:
        print("Failed to create user.")
        print("Db-Error:", e)
        quit()
    except Exception as e:
        print("Failed to create user.")
        print(e)
        return
    print("Created user ", username)


def login_patient(tokens):
    # login_caregiver <username> <password>
    # check 1: if someone's already logged-in, they need to log out first
    global current_patient
    if current_caregiver is not None or current_patient is not None:
        print("User already logged in.")
        return

    # check 2: the length for tokens need to be exactly 3 to include all information (with the operation name)
    if len(tokens) != 3:
        print("Login failed.")
        return

    username = tokens[1]
    password = tokens[2]

    patient = None
    try:
        patient = Patient(username, password=password).get()
    except pymssql.Error as e:
        print("Login failed.")
        print("Db-Error:", e)
        quit()
    except Exception as e:
        print("Login failed.")
        print("Error:", e)
        return

    # check if the login was successful
    if patient is None:
        print("Login failed.")
    else:
        print("Logged in as: " + username)
        current_patient = patient


def login_caregiver(tokens):
    # login_caregiver <username> <password>
    # check 1: if someone's already logged-in, they need to log out first
    global current_caregiver
    if current_caregiver is not None or current_patient is not None:
        print("User already logged in.")
        return

    # check 2: the length for tokens need to be exactly 3 to include all information (with the operation name)
    if len(tokens) != 3:
        print("Login failed.")
        return

    username = tokens[1]
    password = tokens[2]

    caregiver = None
    try:
        caregiver = Caregiver(username, password=password).get()
    except pymssql.Error as e:
        print("Login failed.")
        print("Db-Error:", e)
        quit()
    except Exception as e:
        print("Login failed.")
        print("Error:", e)
        return

    # check if the login was successful
    if caregiver is None:
        print("Login failed.")
    else:
        print("Logged in as: " + username)
        current_caregiver = caregiver


def search_caregiver_schedule(tokens):
    if current_caregiver is None and current_patient is None:
        print("Please login first!")
        return

    if len(tokens) != 2:
        print("Please try again!")
        return

    date = tokens[1]
    # assume input is hyphenated in the format mm-dd-yyyy
    date_tokens = date.split("-")
    month = int(date_tokens[0])
    day = int(date_tokens[1])
    year = int(date_tokens[2])
    try:
        d = datetime.datetime(year, month, day)
        print_availability(d)

    except Exception as E:
        print(E)
        print("Please try again!")


def reserve(tokens):
    if current_caregiver is None and current_patient is None:
        print("Please login first!")
        return

    if current_patient is None:
        print("Please login as a patient first!")
        return

    if len(tokens) != 3:
        print("Please try again!")
        return

    date = tokens[1]
    # assume input is hyphenated in the format mm-dd-yyyy
    date_tokens = date.split("-")
    month = int(date_tokens[0])
    day = int(date_tokens[1])
    year = int(date_tokens[2])

    try:
        d = datetime.datetime(year, month, day)

        caregiver = get_available_caregiver(d)
        if (caregiver is None):
            print("No caregiver is available!")
            return

        vaccine = Vaccine(tokens[2], 0).get()
        if vaccine is None or vaccine.get_available_doses() < 1:
            print("Not enough available doses!")
            return

        create_appointment(d, caregiver, vaccine, current_patient.get_username())
    except Exception as E:
        print(str(E))
        print("Please try again!")


def upload_availability(tokens):
    #  upload_availability <date>
    #  check 1: check if the current logged-in user is a caregiver
    global current_caregiver
    if current_caregiver is None:
        print("Please login as a caregiver first!")
        return

    # check 2: the length for tokens need to be exactly 2 to include all information (with the operation name)
    if len(tokens) != 2:
        print("Please try again!")
        return

    date = tokens[1]
    # assume input is hyphenated in the format mm-dd-yyyy
    date_tokens = date.split("-")
    month = int(date_tokens[0])
    day = int(date_tokens[1])
    year = int(date_tokens[2])
    try:
        d = datetime.datetime(year, month, day)
        current_caregiver.upload_availability(d)
    except pymssql.Error as e:
        print("Upload Availability Failed")
        print("Db-Error:", e)
        quit()
    except ValueError:
        print("Please enter a valid date!")
        return
    except Exception as e:
        print("Error occurred when uploading availability")
        print("Error:", e)
        return
    print("Availability uploaded!")


def cancel(tokens):
    if current_caregiver is None and current_patient is None:
        print("Please login first!")
        return

    if len(tokens) != 2:
        print("Please try again!")
        return

    try:
        delete_appointment(tokens[1])
    except Exception as e:
        print("Error:", e)
        return
    print("Appointment cancelled!")

def add_doses(tokens):
    #  add_doses <vaccine> <number>
    #  check 1: check if the current logged-in user is a caregiver
    global current_caregiver
    if current_caregiver is None:
        print("Please login as a caregiver first!")
        return

    #  check 2: the length for tokens need to be exactly 3 to include all information (with the operation name)
    if len(tokens) != 3:
        print("Please try again!")
        return

    vaccine_name = tokens[1]
    doses = int(tokens[2])
    vaccine = None
    try:
        vaccine = Vaccine(vaccine_name, doses).get()
    except pymssql.Error as e:
        print("Error occurred when adding doses")
        print("Db-Error:", e)
        quit()
    except Exception as e:
        print("Error occurred when adding doses")
        print("Error:", e)
        return

    # if the vaccine is not found in the database, add a new (vaccine, doses) entry.
    # else, update the existing entry by adding the new doses
    if vaccine is None:
        vaccine = Vaccine(vaccine_name, doses)
        try:
            vaccine.save_to_db()
        except pymssql.Error as e:
            print("Error occurred when adding doses")
            print("Db-Error:", e)
            quit()
        except Exception as e:
            print("Error occurred when adding doses")
            print("Error:", e)
            return
    else:
        # if the vaccine is not null, meaning that the vaccine already exists in our table
        try:
            vaccine.increase_available_doses(doses)
        except pymssql.Error as e:
            print("Error occurred when adding doses")
            print("Db-Error:", e)
            quit()
        except Exception as e:
            print("Error occurred when adding doses")
            print("Error:", e)
            return
    print("Doses updated!")


def show_appointments(tokens):
    if current_caregiver is None and current_patient is None:
        print("Please login first!")
        return

    # Assume that only one user is logged in at a time
    try:
        if (current_caregiver is not None):
            current_caregiver.show_appointments()

        if (current_patient is not None):
            current_patient.show_appointments()
    except:
        print("Please try again!")


def logout(tokens):
    global current_patient
    global current_caregiver
    if current_caregiver is None and current_patient is None:
        print("Please login first.")
        return

    current_patient = None
    current_caregiver = None
    print("Successfully logged out!")


def start():
    stop = False
    print()
    print(" *** Please enter one of the following commands *** ")
    print("> create_patient <username> <password>")  # //TODO: implement create_patient (Part 1)
    print("> create_caregiver <username> <password>")
    print("> login_patient <username> <password>")  # // TODO: implement login_patient (Part 1)
    print("> login_caregiver <username> <password>")
    print("> search_caregiver_schedule <date>")  # // TODO: implement search_caregiver_schedule (Part 2)
    print("> reserve <date> <vaccine>")  # // TODO: implement reserve (Part 2)
    print("> upload_availability <date>")
    print("> cancel <appointment_id>")  # // TODO: implement cancel (extra credit)
    print("> add_doses <vaccine> <number>")
    print("> show_appointments")  # // TODO: implement show_appointments (Part 2)
    print("> logout")  # // TODO: implement logout (Part 2)
    print("> Quit")
    print()
    while not stop:
        response = ""
        print("> ", end='')

        try:
            original_response = str(input())
        except ValueError:
            print("Please try again!")
            break

        response = original_response.lower()
        tokens = response.split(" ")
        if len(tokens) == 0:
            ValueError("Please try again!")
            continue
        operation = tokens[0]
        if operation == "create_patient":
            tokens = original_response.split(" ")
            create_patient(tokens)
        elif operation == "create_caregiver":
            tokens = original_response.split(" ")
            create_caregiver(tokens)
        elif operation == "login_patient":
            login_patient(tokens)
        elif operation == "login_caregiver":
            login_caregiver(tokens)
        elif operation == "search_caregiver_schedule":
            search_caregiver_schedule(tokens)
        elif operation == "reserve":
            reserve(tokens)
        elif operation == "upload_availability":
            upload_availability(tokens)
        elif operation == "cancel":
            cancel(tokens)
        elif operation == "add_doses":
            add_doses(tokens)
        elif operation == "show_appointments":
            show_appointments(tokens)
        elif operation == "logout":
            logout(tokens)
        elif operation == "quit":
            print("Bye!")
            stop = True
        else:
            print("Invalid operation name!")


if __name__ == "__main__":
    '''
    // pre-define the three types of authorized vaccines
    // note: it's a poor practice to hard-code these values, but we will do this ]
    // for the simplicity of this assignment
    // and then construct a map of vaccineName -> vaccineObject
    '''

    # start command line
    print()
    print("Welcome to the COVID-19 Vaccine Reservation Scheduling Application!")

    start()
