import logging
from bs4 import BeautifulSoup
import requests
import time
import datetime

def date_convert(time_str:str)->datetime:
    dateOb = datetime.datetime.strptime(time_str, "%a, %d %b %Y %H:%M:%S %Z")
    return dateOb

def get_articles(result:BeautifulSoup, cat:str, source:str, logger:logging, NewArticle)->list:
    """[Ingest XML of summary page for articles info]

    Args:
        result (BeautifulSoup object): html of apartments page
        cat (str): category being searched
        source (str): source website
        logger (logging.logger): logger for Kenny loggin
        NewArticle (dataclass) : Dataclass object for NewsArticle

    Returns:
        articles (list): [List of NewArticle objects]
    """

    articles = []
    article_id = creator = author = title = description = url = pub_date = current_time = None

    #Set the outer loop over each card returned. 
    for child in result.contents:
        #Description not available.  Putting regional info here
        if child.name == "h2" or child.name == "h3":
            descript = child.find("em").text
            continue
        if not child.name:
            continue

        # Time of pull
        current_time = time.strftime("%m-%d-%Y_%H-%M-%S")
        
        # grab creator
        creator = child.find("em").text

        # Grab the author
        if "By" in child.text:
            author = child.text.split("\n")[1].strip("By ")
        else:
            author = None
            
        
        #Put section in description
        description = descript

        #grab the title
        title = description + " - " + creator + " - " + child.find("a").text
        
        #grab the url
        url = child.find("a").get("href")

        #use url as key. #I know, messy, but there isn't a unique id stored on the page.
        article_id = url
        
        #Not available either without digesting the downstream link
        pub_date = datetime.datetime.now()

        article = NewArticle(
            id=article_id,
            source=source,
            creator=creator,
            author=author,
            title=title,
            description=description,
            link=url,
            category=cat,
            pub_date=pub_date,
            pull_date=current_time
        )
        articles.append(article)
        article_id = creator = author = title = description = url = pub_date = current_time = None
    
    return articles

def ingest_xml(cat:str, source:str, logger:logging, NewArticle)->list:
    """[Outer scraping function to set up request pulls]

    Args:
        cat (str): category of site to be searched
        source (str): RSS feed origin
        logger (logging.logger): logger for Kenny loggin
        NewArticle (dataclass): Custom data object

    Returns:
        new_articles (list): List of dataclass objects
    """
    dt = datetime.datetime.now()
    day = dt.day
    weekend = dt.weekday() > 4
    if weekend:
        logger.info("AILA only posts on weekdays. No soup for you!")
        return None
    
    month = dt.strftime("%B").lower()
    year = dt.year
    feeds = {
        "AILA Daily News Update":f"https://www.aila.org/library/daily-immigration-news-clips-{month}-{day}-{year}",
        #"Aaila Blog"           :f"https://www.aila.org/library/daily-immigration-news-clips-march-6-2025",
    }
    # 

    new_articles = []
    url = feeds.get(cat)
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
    if url:
        response = requests.get(url, headers=headers)
    else:
        raise ValueError("Your URL isn't being loaded correctly")
    
    #Trap the not found specifically return because it looks like they don't post this until later in the day.  
        #So this might not be a good morning news source. 

    if response.status_code == 404:
        logger.warning(f'Status code: {response.status_code}')
        logger.warning(f'Reason: {response.reason}')
        logger.warning(f"Daily news not up yet for {source}.  Check again later")
        return None
    
    #Just in case we piss someone off
    if response.status_code != 200:
        # If there's an error, log it and return no data for that site
        logger.warning(f'Status code: {response.status_code}')
        logger.warning(f'Reason: {response.reason}')
        return None

    #Parse the XML
    bs4ob = BeautifulSoup(response.text, features="lxml")

    #Find all records (item CSS)
    results = bs4ob.find("div", class_="typography text rte")
    if results:
        new_articles = get_articles(results, cat, source, logger, NewArticle)
        logger.debug(f'{len(new_articles)} articles returned from {source}')
        return new_articles
            
    else:
        logger.info(f"No articles returned on {source} / {cat}.  Moving to next feed")

#Bex suggestions.  
#Anywway to filter specifically for chicago based immigration news. 
#Also wants to filter out asylum and removal updates.  Not sure how that might work. 

#root url
#https://www.aila.org/immigration-news
#
# Basic URl structure of searching postings
#https://www.aila.org/recent-postings?FromDate=2025-02-28&ToDate=2025-03-07&limit=50

#Lol.  Or i caould just grab the hardcoded 
#news summary they already have
#https://www.aila.org/library/daily-immigration-news-clips-march-6-2025
#Def doing that. 
