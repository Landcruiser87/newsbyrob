import logging
from bs4 import BeautifulSoup
import requests
import time
from typing import Union

def get_listings(result:BeautifulSoup, neigh:str, source:str, logger:logging, NewArticle)->list:
    """[Ingest XML of summary page for articles info]

    Args:
        result (BeautifulSoup object): html of apartments page
        neigh (str): neighorhood being searched
        source (str): Source website
        logger (logging.logger): logger for Kenny loggin
        NewArticle (dataclass) : Dataclass object for news article

    Returns:
        articles (list): [List of NewArticle objects]
    """

    articles = []
    listingid = price = beds = sqft = baths = pets = url = addy = current_time = None

    #Set the outer loop over each card returned. 
    for card in result.find_all("li", class_="placard-container"):
        # Time of pull
        current_time = time.strftime("%m-%d-%Y_%H-%M-%S")

        #Grab the id
        search = card.find("article", "search-placard for-rent-mls-placard")
        if search:
            listingid = search.get("data-pk")
        else:
            logger.warning(f"missing id for card on {source} in {neigh}")
            continue

        details = card.find("div", class_="for-rent-content-container")
        if details:
            #grab address
            res = card.find("p", class_="address")
            if res:
                addy = res.text
            #grab url
            res = card.find("a")
            if res:
                url = "https://" + source + res.get("href")

            search = card.find("ul", class_="detailed-info-container")
            for subsearch in search.find_all("li"):
                testval = subsearch.text
                if testval:
                    #Grab price
                    if "$" in testval:
                        price = int("".join(x for x in testval if x.isnumeric()))
                    #Grab Beds
                    elif "beds" in testval.lower():
                        beds = int("".join(x for x in testval if x.isnumeric()))
                    #Grab baths
                    elif "baths" in testval.lower():
                        baths = int("".join(x for x in testval if x.isnumeric()))
                    #! SQFT is available on the individual links, but not worth
                    #! the extra call to grab it

        pets = True

        listing = NewArticle(
            id=listingid,
            source=source,
            price=price,
            neigh=neigh,
            bed=beds,
            sqft=sqft,
            bath=baths,
            dogs=pets,
            link=url,
            address=addy,
            date_pulled=current_time
        )
        articles.append(listing)
        listingid = price = beds = sqft = baths = pets = url = addy = current_time = None

    return articles

def ingest_xml(cat:str, source:str, logger:logging, NewArticle)->list:
    """[Outer scraping function to set up request pulls]

    Args:
        cat (str): category of site to be searched
        source (str): RSS feed origin
        logger (logging.logger): logger for Kenny loggin
        NewArticle (dataclass): Custom data object

    Returns:
        property_listings (list): List of dataclass objects
    """
    feeds = {
        "Travel updates"          :"https://www.cbp.gov/rss/travel",
        "Trusted traveler updates":"https://www.cbp.gov/rss/ttp",
        "Border Security updates" :"https://www.cbp.gov/rss/border-security"
    }

    url = feeds.get(cat)

    #Error Trapping
    # else:
    #     logger.critical("Inproper input for area, moving to next site")
    #     return
 
    headers = {
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="122", "Chromium";v="122"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'referer': url,
        'origin':source,
        'Content-Type': 'text/html,application/xhtml+xml,application/xml'
    }

    response = requests.get(url, headers=headers)

    #Just in case we piss someone off
    if response.status_code != 200:
        # If there's an error, log it and return no data for that site
        logger.warning(f'Status code: {response.status_code}')
        logger.warning(f'Reason: {response.reason}')
        return None

    #Get the HTML
    bs4ob = BeautifulSoup(response.text, 'lxml')

    # Isolate the property-list from the expanded one (I don't want the 3 mile
    # surrounding.  Just the neighborhood)
    nores = bs4ob.find_all("div", class_="no-results-container")
    if not nores:
        results = bs4ob.find("section", class_="placards")
        if results:
            if results.get("id") =='placardContainer':
                property_listings = get_listings(results, neigh, source, logger, Propertyinfo)
                logger.info(f'{len(property_listings)} articles returned from {source}')
                return property_listings
            
    else:
        logger.warning("No articles returned on apartments.  Moving to next site")
