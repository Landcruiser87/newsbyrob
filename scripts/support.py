import datetime
import numpy as np
import time
import json
from os.path import exists
import logging

#Progress bar fun
from rich.progress import (
    Progress,
    BarColumn,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn
)
from rich.logging import RichHandler
from rich.align import Align
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console
from pathlib import Path


################################# Emailing Funcs ####################################

#FUNCTION URL Format
def urlformat(urls:list)->str:
    """This formats each of the list items into an html list for easy ingestion into the email server

    Args:
        urls (list): List of new listings found

    Returns:
        str: HTML formatted string for emailing
    """	
    
    links_html = "<ol>"
    if len(urls) > 1:
        for link, site, cat, title in urls:
            links_html += f"<li><a href='{link}'> {site} - {cat} - {title} </a></li>"
    else:
        links_html = f"<li><a href='{urls[0][0]}'> {urls[0][1]} - {urls[0][2]} - {urls[0][3]} </a></li>"
    links_html = links_html + "</ol>"
    return links_html

#FUNCTION Send email update
def send_email_update(urls:str):
    """[Function for sending an email.  Formats the url list into a basic email with said list]

    Args:
        url (str): [url of the news story]

    Returns:
        [None]: [Just sends the email.  Doesn't return anything]
    """	
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    def inputdatlink(urls:str):
        html = """
        <html>
            <body>
                <p>Greetings!<br>
                Rob wanted you to look at these new articles!<br>
                """ + urls + """
                </p>
            </body>
        </html>
        """
        return html

    with open('./secret/login.txt') as login_file:
        login = login_file.read().splitlines()
        sender_email = login[0].split(':')[1]
        password = login[1].split(':')[1]
        receiver_email = login[2].split(':')[1].split(",")
        
    # Establish a secure session with gmail's outgoing SMTP server using your gmail account
    smtp_server = "smtp.gmail.com"
    port = 465
    html = inputdatlink(urls)

    message = MIMEMultipart("alternative")
    message["Subject"] = "Immigration Updates ala Rob!"
    message["From"] = sender_email
    message["To"] = ", ".join(receiver_email)   
    attachment = MIMEText(html, "html")
    message.attach(attachment)
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)		
        server.sendmail(sender_email, receiver_email, message.as_string())

################################# Logging Funcs ####################################

def get_file_handler(log_dir:Path)->logging.FileHandler:
    """Assigns the saved file logger format and location to be saved

    Args:
        log_dir (Path): Path to where you want the log saved

    Returns:
        filehandler(handler): This will handle the logger's format and file management
    """	
    LOG_FORMAT = "%(asctime)s|%(levelname)-8s|%(lineno)-3d|%(funcName)-14s|%(message)s|" 
    current_date = time.strftime("%m-%d-%Y_%H-%M-%S")
    log_file = log_dir / f"{current_date}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, "%m-%d-%Y %H:%M:%S"))
    return file_handler

def get_rich_handler(console:Console):
    """Assigns the rich format that prints out to your terminal

    Args:
        console (Console): Reference to your terminal

    Returns:
        rh(RichHandler): This will format your terminal output
    """
    FORMAT_RICH = "|%(funcName)-14s|%(message)s "
    rh = RichHandler(level=logging.INFO, console=console)
    rh.setFormatter(logging.Formatter(FORMAT_RICH))
    return rh

def get_logger(log_dir:Path, console:Console)->logging.Logger:
    """Loads logger instance.  When given a path and access to the terminal output.  The logger will save a log of all records, as well as print it out to your terminal. Propogate set to False assigns all captured log messages to both handlers.

    Args:
        log_dir (Path): Path you want the logs saved
        console (Console): Reference to your terminal

    Returns:
        logger: Returns custom logger object.  Info level reporting with a file handler and rich handler to properly terminal print
    """	
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(get_file_handler(log_dir)) 
    logger.addHandler(get_rich_handler(console))  #Was causing flickering error in the rendering because the log statments kept trying to print
    logger.propagate = False
    return logger

#CLASS Numpy encoder
class NumpyArrayEncoder(json.JSONEncoder):
    """Custom numpy JSON Encoder.  Takes in any type from an array and formats it to something that can be JSON serialized.
    Source Code found here.  https://pynative.com/python-serialize-numpy-ndarray-into-json/
    Args:
        json (object): Json serialized format
    """	
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, str):
            return obj
        elif isinstance(obj, datetime.datetime):
            return datetime.datetime.strftime(obj, "%m-%d-%Y_%H-%M-%S")
        else:
            return super(NumpyArrayEncoder, self).default(obj)
        
################################# Rich Spinner Control ####################################

#FUNCTION sleep progbar
def mainspinner(console:Console, totalstops:int):
    my_progress_bar = Progress(
        TextColumn("{task.description}"),
        SpinnerColumn("pong"),
        BarColumn(),
        TextColumn("*"),
        "time elapsed:",
        TextColumn("*"),
        TimeElapsedColumn(),
        TextColumn("*"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        transient=True,
        console=console,
        refresh_per_second=10
    )
    jobtask = my_progress_bar.add_task("[green]Checking RSS Feeds", total=totalstops)
    return my_progress_bar, jobtask

def add_spin_subt(prog:Progress, msg:str, howmanysleeps:int):
    liljob = prog.add_task(f"[magenta]{msg}", total = howmanysleeps)
    for _ in range(howmanysleeps):
        time.sleep(1)
        prog.update(liljob, advance=1)
    prog.update(liljob, visible=False)


################################# Date/Load/Save Funcs ####################################

#FUNCTION Convert Date
def date_convert(str_time:str)->datetime:
    dateOb = datetime.datetime.strptime(str_time,'%m-%d-%Y_%H-%M-%S')
    return dateOb

#FUNCTION Save Data
def save_data(jsond:dict):
    #Sort by published date
    sorted_dict = dict(sorted(jsond.items(), key=lambda x:datetime.datetime.strftime(x[1]["pub_date"], "%Y-%m-%d").split("-"), reverse=True))
    out_json = json.dumps(sorted_dict, indent=2, cls=NumpyArrayEncoder)
    with open("./data/im_updates.json", "w") as out_f:
        out_f.write(out_json)

#FUNCTION Load Historical
def load_historical(fp:str)->json:
    if exists(fp):
        with open(fp, "r") as f:
            jsondata = json.loads(f.read())
            #Quick format the pub date strings back to dates. 
            #We need them as dates to sort them on the save above.
            for key in jsondata.keys():
                jsondata[key]["pub_date"] = date_convert(jsondata[key]["pub_date"])
            return jsondata	
