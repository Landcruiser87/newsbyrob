import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import requests
import time
import datetime

def date_convert(time_str:str)->datetime:
    # _.strftime("%a, %d %b %y %H:%M:%S %z") #To verify correct converstion
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
        if child.name == "h2":
            descript = child.find("em").text
            continue
        if not child.name:
            continue

        # Time of pull
        current_time = time.strftime("%m-%d-%Y_%H-%M-%S")
        
        # grab creator
        creator = child.find("a").text

        # Grab the author
        author = child.text.split("\n")[1].strip("By ")

        #grab the title
        title = child.find("a").text
        
        #Put section in description
        description = descript
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
        article_id = creator = author = title = description = url = pub_date =  current_time = None
    
    return articles

def get_html(url:str, logger:logging):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            response = page.goto(url)
            if response.status != 200:
                logger.warning(f"Status code: {response.status}")
                logger.warning(f"Status text: {response.status_text}")
                return None

            page.wait_for_selector("body", timeout=15000)
            html = page.content()
            return html
        except Exception as e:
            logger.warning(f"Error: {e}")
            return None
        finally:
            browser.close()

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
    feeds = {
        "Boundless Blog"  :"https://www.boundless.com/blog/category/immigration-news/",
        # "Boundless Weekly":"https://www.boundless.com/blog/boundless-weekly-immigration-news/"
    }
    new_articles = []
    url = feeds.get(cat)
    if url:
        try:
            response = get_html(url, logger)

        except Exception as e:
            logger.warning(f"Error on {url}\n\n{e}")
            return None

    #Parse the XML
    if response:
        bs4ob = BeautifulSoup(response.text, features="lxml")

        #Find all records (item CSS)
        results = bs4ob.find_all("article", class_=lambda x: x and x.startswith("o-grid"))
        if results:
            new_articles = get_articles(results, cat, source, logger, NewArticle)
            logger.info(f'{len(new_articles)} articles returned from {source}')
            return new_articles
    else:
        logger.warning(f"No articles returned on {source} / {cat}.  Moving to next feed")
