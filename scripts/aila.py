import logging
from bs4 import BeautifulSoup
import requests
import time
import datetime

def date_convert(time_str:str)->datetime:
    # _.strftime("%a, %d %b %y %H:%M:%S %z") #To verify correct converstion
    dateOb = datetime.datetime.strptime(time_str, "%a, %d %b %Y %H:%M:%S %Z")
    return dateOb

def get_articles(results:BeautifulSoup, cat:str, source:str, logger:logging, NewArticle)->list:
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
    article_id = creator = title = description = url = pub_date = current_time = None

    #Set the outer loop over each card returned. 
    for card in results:
        # Time of pull
        current_time = time.strftime("%m-%d-%Y_%H-%M-%S")
        
        card_contents = card.contents
        for row in card_contents:
            rname = row.name
            if row == "\n":
                continue
            elif rname == "title":
                title = row.text
            elif rname == "link":
                url = row.text
            elif rname == "description":
                description = row.text
            elif rname == "pubDate":
                pub_date = date_convert(row.text)
            elif rname == "source url":
                creator = row.text
            elif rname == "guid":
                article_id = row.text
            
        article = NewArticle(
            id=article_id,
            source=source,
            creator=creator,
            title=title,
            description=description,
            link=url,
            category=cat,
            pub_date=pub_date,
            pull_date=current_time
        )
        articles.append(article)
        article_id = creator = title = description = url = pub_date =  current_time = None
    
    return sorted(articles, key=lambda x:x.pub_date)[:5] 

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
    month = dt.month
    year = dt.year
    feeds = {
        "Aila daily news":f"https://www.aila.org/library/daily-immigration-news-clips-{month}-{day}-{year}",
        # "Aaila Blog"   :f"https://www.aila.org/library/daily-immigration-news-clips-march-6-2025",
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
    
    #Just in case we piss someone off
    if response.status_code != 200:
        # If there's an error, log it and return no data for that site
        logger.warning(f'Status code: {response.status_code}')
        logger.warning(f'Reason: {response.reason}')
        return None

    #Parse the XML
    bs4ob = BeautifulSoup(response.text, features="xml")

    #Find all records (item CSS)
    results = bs4ob.find_all("item")
    if results:
        new_articles = get_articles(results, cat, source, logger, NewArticle)
        logger.info(f'{len(new_articles)} articles returned from {source}')
        return new_articles
            
    else:
        logger.warning(f"No articles returned on {source} / {cat}.  Moving to next feed")


#root url
#https://www.aila.org/immigration-news
#
# Basic URl structure of searching postings
#https://www.aila.org/recent-postings?FromDate=2025-02-28&ToDate=2025-03-07&limit=50

#Lol.  Or i caould just grab the hardcoded 
#news summary they already have
#https://www.aila.org/library/daily-immigration-news-clips-march-6-2025
#Def doing that. 
