import smtplib

# ------------------ CONSTANTS ------------------ #
DEFAULT_EMAIL = "jamersonjimmy529@gmail.com"
DEFAULT_API = "hmmfcjctlallahda"


# ------------------ CLASS ------------------ #
class Emailer:
    def __init__(self, email=DEFAULT_EMAIL, api_key=DEFAULT_API):
        self.email = email
        self.api_key = api_key

    def send_message(self, subject, message, to_address="dnolte1224@gmail.com"):
        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:  # builds the connection configured for our source email server type (gmail)
            connection.starttls()   # transfer layer security - encrypts the message in transit
            connection.login(user=self.email, password=self.api_key)  # the source email name, and google api key
            connection.sendmail(from_addr=self.email, to_addrs=f"{to_address}"
                                , msg=f"Subject:{subject}\n\n"  # subject line
                                      f"{message}")  # body of the email
