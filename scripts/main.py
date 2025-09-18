#Import libraries
import numpy as np
import datetime
import logging
from rich.console import Console
from rich.progress import Progress
from dataclasses import dataclass
from os.path import exists

import uscis, travel, ice, g_news, aila, boundless, support #cbp,
from support import log_time, logger, console, move_log

################################# Global Variable Setup ####################################
SITES = {
    "USCIS"    : ("https://www.uscis.gov", uscis),
    "DOS"      : ("https://travel.state.gov", travel),
    "Boundless": ("https://www.boundless.com", boundless),
    "Google"   : ("https://www.news.google.com", g_news),
    "AILA"     : ("https://www.aila.org", aila),    
    "ICE"      : ("https://www.ice.gov", ice),
    # "CBP"    : ("https://www.cbp.gov", cbp),  #Sunsetting CBP 3-7-25.  They basically only report finding drugs at the border
}

CATEGORIES = {
    "USCIS"    : ["Fact Sheets", "News Releases", "Stakeholder Messages", "Alerts", "Forms Updates"], 
    "DOS"      : ["main_feed"], 
    "Boundless": ["Boundless Blog"], #, "Boundless Weekly"
    "Google"   : ["US Immigration Changes", "USCIS Updates"],
    "AILA"     : ["AILA Daily News Update"],
    "ICE"      : ["Management and Administration", "Operational", "Profesional Responsibility", "National Security", "Partnership and Engagement", "Enforcement and Removal", "Transnational Gangs"]
    #"CBP"     : ["Travel updates","Trusted traveler updates","Border Security","Newsroom"], #"Border wait time feeds" currently down, Also security might be redundant here
}

#Define dataclass container
@dataclass
class NewArticle():
    id          : str = None
    source      : str = None
    creator     : str = None
    author      : str = None
    title       : str = None
    description : str = None
    link        : str = None
    category    : str = None
    pub_date    : datetime.datetime = ""
    pull_date   : datetime.datetime = ""
    identifier  : str = ""
    threat_level: str = ""
    country     : str = ""
    keyword     : str = ""

################################# Main Funcs ####################################
#FUNCTION Add Data
def add_data(data:list, site:str, cat:str):
    """Adds data to JSON Historical file

    Args:
        data (list): List of NewArticle objects that are new (not in the historical)
        siteinfo (tuple): Tuple of website and category
    """	
    ids = [data[x].id for x in range(len(data))]
    #Reshape data to dict
    #make a new dict that can be json serialized with the id as the key
    new_dict = {data[x].id : data[x].__dict__ for x in range(len(data))}
    #Pop the id from the dict underneath (no need to store it twice)
    [new_dict[x].pop("id") for x in ids]
    if site != "DOS":
        for val in ["identifier","threat_level","country","keyword" ]:
            [new_dict[x].pop(val) for x in ids]

    #update main data container
    jsondata.update(new_dict)
    
    #make tuples of (urls, site, category, title) for emailing
    newurls = [(new_dict[idx].get("link"), site, cat, new_dict[idx].get("title")) for idx in new_dict.keys()]
    #Extend the newstories global list
    newstories.extend(newurls)

    logger.info(f"data added for {site} in {cat}")
    logger.info(f"These ids were added or altered\n{ids}")
    
#FUNCTION Check IDs
def check_ids(data:list):
    """This function takes in a list of NewArticle objects, reformats them to a
    dictionary, compares the id's to existing JSON historical id keys, finds
    any new ones via set comparison. Then returns a list of NewArticle objects
    that have those new id's (if any)

    Args:
        data (list): List of NewArticle objects

    Returns:
        data (list): List of only new NewArticle objects
    """	
    #Set comparison of jsondata ids and new data ids
    j_ids = set(jsondata.keys())
    n_ids = set([data[x].id for x in range(len(data))])
    newids = n_ids - j_ids
    if newids:
        #Only add the articles that are new.  
        newdata = []
        [newdata.append(data[idx]) for idx, _ in enumerate(data) if data[idx].id in newids]
        return newdata
    else:
        logger.info("Articles(s) already stored in im_updates.json") 
        return None

#FUNCTION Check Changes
def check_changes(data:list)->list:
    """For DOS, we want to track when a record changes, this function examines the
    title and description of each country's travel status.  If either is
    different in any way, then the record flagged for updating when
    the data is added to the jsondata container.

    Args:
        data (list): List of NewArticle objects]

    Returns:
        newdata (list): list of new ids
    """    
    newdata = []
    for newarticle in data:
        if newarticle.id in jsondata.keys():
            title = jsondata[newarticle.id]["title"]
            descript = jsondata[newarticle.id]["description"]
            if (newarticle.description != descript) | (newarticle.title != title):
                logger.warning(f"Updated information found for\n{newarticle.title}\n{newarticle.id} ")
                newdata.append(newarticle)
        else:
            #if key doesn't exist in the jsondata container, add the record
            newdata.append(newarticle)
    if newdata:
        return newdata
    else:
        logger.info("No updates from article(s) stored in im_updates.json") 
        return None

#FUNCTION Parse Feed
def parse_feed(site:str, siteinfo:tuple, prog:Progress, jobtask:int):
    """This function will iterate through different categories on each RSS feed. Ingesting
    only the material that we deem important

    Args:
        site (str): abbrev RSS feed we want to ingest
        siteinfo (tuple): Tuple of site address and site file we want to run
        prog (Progress): Overall progress bar
        jobtask (int): jobid for the main overall task
    """
    for cat in CATEGORIES.get(site):
        if cat:
            # Update and advance the overall progressbar
            prog.update(task_id=jobtask, description=f"[green]{site}:{cat}", advance=1)
            logger.info(f"Parsing {site} for {cat}")
            data = siteinfo[1].ingest_xml(cat, siteinfo[0], NewArticle)

            #Take a lil nap.  Be nice to the servers!
            support.add_spin_subt(prog, "server nap", np.random.randint(3, 6))

            #If data was returned
            if data:
                #These functions will isolate new id's that aren't in the historical JSON
                if site != "DOS":
                    datacheck = check_ids(data)
                else:
                    datacheck = check_changes(data)

                if datacheck:
                    logger.info(f"New data found, cleaning and storing {len(datacheck)} new links")
                    data = datacheck
                    del datacheck

                    #Add the articles to the jsondata dict. 
                    add_data(data, site, cat)
                    del data
            else:
                logger.info(f"No new data found on {site}")

        else:
            logger.warning(f"{site} is not in validated search list")

################################# Start Program ####################################
@log_time
def main():
    global newstories, jsondata
    newstories = []
    fp = "./data/im_updates.json"
    totalstops = sum([len(x) for x in CATEGORIES.values()])

    #Load im_updates.json
    if exists(fp):
        jsondata = support.load_historical(fp)
        logger.info("historical data loaded")
    else:
        jsondata = {}
        logger.warning("No historical data found")

    prog, task = support.mainspinner(console, totalstops)
    with prog:
        for site, info in SITES.items():
            parse_feed(site, info, prog, task)

    if newstories:
        # If new articles are found, save the data to the json file, 
        # format the list of dataclassses to a url 
        # Send gmail alerting of new articles
        # support.save_data(jsondata)
        links_html = support.urlformat(newstories)
        # support.send_email_update(links_html)
        logger.warning(f"{len(newstories)} new articles found.  Email sent")

    else:
        logger.critical("No new articles were found")
    
    logger.info("Program shutting down")

if __name__ == "__main__":
    main()
    logging.shutdown()
    move_log()

#Certain enterprise accounts will allow less secure passwords, but disabled since 2022 way around is here.
#https://stackoverflow.com/questions/73365098/how-to-turn-on-less-secure-app-access-on-google
#generate an app password and use that as your login. 
#Needs 2fa enabled to work
