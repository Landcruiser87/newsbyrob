#Import libraries
import numpy as np
import logging
import time
# from rich.logging import RichHandler
# from rich.live import Live
from rich.console import Console
from dataclasses import dataclass, field
from os.path import exists
from random import shuffle
from pathlib import Path, PurePath
import uscis, cbp, travel, ice, support

################################# Global Variable Setup ####################################
SITES = {
    "DOS"  : ("https://travel.state.gov", travel),
    "USCIS": ("https://www.uscis.gov", uscis),
    "CBP"  : ("https://www.cbp.gov", cbp),
    # "ICE"   : ("https://www.ice.gov", ice),
}

CATEGORIES = {
    "DOS"  : ["main_feed"],
    "USCIS": ["Fact Sheets", "News Releases", "Stakeholder Messages", "Alerts"], 
    "CBP"  : ["Travel updates","Trusted traveler updates", "Border Security updates"], #"Border wait time feeds" currently down
    # "ICE"   : ["List of cats"],
}


#Define dataclass container
@dataclass
class NewArticle():
    id          : str
    source      : str
    creator     : str
    title       : str
    description : str
    link        : str
    category    : str
    pub_date    : np.datetime64
    date_pulled : np.datetime64
    identifier  : str = ""
    threat_level: str = ""
    country     : str = ""
    keyword     : str = ""
    # L_dist      : float = ""
    # crime_sc    : dict = field(default_factory=lambda:{})

################################# Timing Func ####################################
def log_time(fn):
    """Decorator timing function.  Accepts any function and returns a logging
    statement with the amount of time it took to run. DJ, I use this code everywhere still.  Thank you bud!

    Args:
        fn (function): Input function you want to time
    """	
    def inner(*args, **kwargs):
        tnow = time.time()
        out = fn(*args, **kwargs)
        te = time.time()
        took = round(te - tnow, 2)
        if took <= 60:
            logging.warning(f"{fn.__name__} ran in {took:.2f}s")
        elif took <= 3600:
            logging.warning(f"{fn.__name__} ran in {(took)/60:.2f}m")		
        else:
            logging.warning(f"{fn.__name__} ran in {(took)/3600:.2f}h")
        return out
    return inner

################################# Main Funcs ####################################
#FUNCTION Add Data
def add_data(data:list, siteinfo:tuple):
    """Adds Data to JSON Historical file

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

    #update main data container
    jsondata.update(new_dict)
    
    #make tuples of (urls, site, category) for emailing
    newurls = [(new_dict[idx].get("link"), siteinfo[0], siteinfo[1]) for idx in new_dict.keys()]
    #Extend the newstories global list
    newstories.extend(newurls)

    logger.info("Global dict updated")
    logger.info(f"data added for {siteinfo[0]} in {siteinfo[1]}")

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

#FUNCTION Scrape data
def parse_feed(site:str, siteinfo:tuple):
    """This function will iterate through different categories on each RSS feed. Ingesting
    only the material that we deem important

    Args:
        site (str): abbrev RSS feed we want to ingest
        siteinfo (tuple): Tuple of site address and file to import
    """
    
    for cat in CATEGORIES.get(site):
        if cat:
            #Update and advance the overall progressbar
            # progbar.advance(task)
            # progbar.update(task_id=task, description=f"{neigh}:{site[0]}")
            
            logger.info(f"Parsing {site} for {cat}")
            data = siteinfo[1].ingest_xml(cat, siteinfo[0], logger, NewArticle)

            #Take a lil nap.  Be nice to the servers!
            time.sleep(np.random.randint(4, 6))
            # support.run_sleep(np.random.randint(3,8), f'Napping at {site[0]}', layout)

            #If data was returned
            if data:
                #This function will isolate new id's that aren't in the historical JSON
                datacheck = check_ids(data)
                if datacheck:
                    logger.info(f"New data found, cleaning and storing {len(datacheck)} new links")
                    data = datacheck
                    del datacheck
                    # layout["find_count"].update(support.update_count(len(data), layout))

                    #Add the articles to the jsondata dict. 
                    add_data(data, (site, cat))
                    del data
            else:
                logger.info(f"No new data found on {site}")

        else:
            logger.warning(f"{site} is not in validated search list")

################################# Start Program ####################################

def main():
    global newstories, jsondata
    newstories = []
    fp = "./data/im_updates.json"
    # totalstops = len(CATEGORIES) * len(SITES)

    global logger, console
    console = Console(color_system="auto")
    log_path = PurePath(Path.cwd(), Path("./data/logs"))
    logger = support.get_logger(log_path, console=console)
    # layout, progbar, task, main_table = support.make_rich_display(totalstops)

    #Load rental_list.json
    if exists(fp):
        jsondata = support.load_historical(fp)
        logger.info("historical data loaded")
    else:
        jsondata = {}
        logger.warning("No historical data found")

    # with Live(layout, refresh_per_second=10, screen=True, transient=True) as live:
    #     logger.addHandler(support.MainTableHandler(main_table, layout, logger.level))
    for site, info in SITES.items():
        parse_feed(site, info)
        time.sleep(np.random.randint(3, 6))

    if newstories:
        # If new articles are found, save the data to the json file, 
        # format the list of dataclassses to a url 
        # Send gmail alerting of new articles
        support.save_data(jsondata)
        links_html = support.urlformat(newstories)
        # support.send_email_update(links_html)
        logger.info(f"{len(newstories)} new articles found.  Email sent")

    else:
        logger.critical("No new articles were found")
    
    logger.info("Program shutting down")

if __name__ == "__main__":
    main()
    

