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
    "USCIS" : ("https://www.uscis.gov/news/rss-feed/59144", uscis),
    "CBP"   : ("https://www.cbp.gov/rss", cbp),
    "TRAVEL": ("https://travel.state.gov/_res/rss/TAsTWs.xml#.html", travel),
    "ICE"   : ("https://www.ice.gov/rss", ice)
}

CATEGORIES = {
    "USCIS" : ["List of cats"],
    "CBP"   : ["List of cats"],
    "TRAVEL": ["List of cats"],
    "ICE"   : ["List of cats"]
}


#Define dataclass container
@dataclass
class NewArticle():
    id          : str
    creator     : str
    title       : str
    description : str
    link        : str
    category    : str
    date_pulled : np.datetime64
    L_dist      : float = ""
    crime_sc    : dict = field(default_factory=lambda:{})

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
    
    #make tuples of (urls, site, neighborhood) for emailing
    newurls = [(new_dict[idx].get("link"), siteinfo[0].split(".")[1], (new_dict[idx].get("neigh"))) for idx in new_dict.keys()]
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
        #Only add the listings that are new.  
        newdata = []
        [newdata.append(data[idx]) for idx, _ in enumerate(data) if data[idx].id in newids]
        return newdata
    else:
        logger.info("Listing(s) already stored in rental_list.json") 
        return None

#FUNCTION Scrape data
def scrape(site:tuple):
    """This function will iterate through different categories on each RSS feed. Ingesting
    only the material that we deem important

    Args:
        site (str): RSS feed we want to ingest
    """	
    for cat in CATEGORIES.get(site[0]):
        if cat:
            #Update and advance the overall progressbar
            # progbar.advance(task)
            # progbar.update(task_id=task, description=f"{neigh}:{site[0]}")
            
            logger.info(f"scraping {site[0]} for {neigh}")
            data = site[1].neighscrape(neigh, site[0], logger, NewArticle)

            #Take a lil nap.  Be nice to the servers!
            # support.run_sleep(np.random.randint(3,8), f'Napping at {site[0]}', layout)

            #If data was returned
            if data:
                #This function will isolate new id's that aren't in the historical JSON
                datacheck = check_ids(data)
                if datacheck:
                    logger.info(f"New data found, cleaning and storing {len(datacheck)} new links")
                    #pull the lat long, score it and store it. 
                    data = datacheck
                    del datacheck
                    #Get lat longs for the address's
                    # layout["find_count"].update(support.update_count(len(data), layout))

                    #Add the listings to the jsondata dict. 
                    add_data(data, (site[0], neigh))
                    del data
            else:
                logger.info(f"No new data found on {source}")

        else:
            logger.warning(f"{source} is not in validated search list")


################################# Start Program ####################################

def main():
    global newstories, jsondata
    newstories = []
    fp = "./data/im_updates.json"
    totalstops = len(CATEGORIES) * len(SITES)

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
    for site in SITES:
        scrape(site)

    # If new listings are found, save the data to the json file, 
    # format the list of dataclassses to a url 
    # Send gmail alerting of new properties
    if newstories:
        support.save_data(jsondata)
        links_html = support.urlformat(newstories)
        support.send_housing_email(links_html)
        logger.info(f"{len(newstories)} new articles found.  Email sent")

    else:
        logger.critical("No new listings were found")
    
    logger.info("Program shutting down")

if __name__ == "__main__":
    main()
    

