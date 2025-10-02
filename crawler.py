import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import re
from collections import deque
import threading

class WebCrawler:
    def __init__(self, max_pages=100, delay=1):
        self.max_pages = max_pages
        self.delay = delay
        self.visited_urls = set()
        self.to_visit = deque()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; MiniGoogleBot/1.0)'
        })
        
    def is_valid_url(self, url):
        """Check if URL is valid for crawling"""
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        # Avoid non-content URLs
        if any(ext in parsed.path.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.zip']):
            return False
        return True
    
    def extract_links(self, html, base_url):
        """Extract all links from HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(base_url, href)
            if self.is_valid_url(full_url):
                links.append(full_url)
                
        return links
    
    def extract_content(self, html, url):
        """Extract meaningful content from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Try to get title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        else:
            # Try h1 as fallback
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text().strip()
        
        # Get main content - try article, main, or body
        content_elements = soup.find_all(['article', 'main', 'div'], class_=re.compile(r'content|main|article', re.I))
        if not content_elements:
            content_elements = [soup.find('body')]
        
        content_text = ""
        for element in content_elements:
            if element:
                text = element.get_text()
                # Clean up text
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                content_text += text + " "
        
        return title, content_text.strip()
    
    def crawl(self, start_urls, search_engine, max_depth=2):
        """Start crawling from given URLs"""
        self.to_visit.extend([(url, 0) for url in start_urls])
        doc_id = 0
        
        while self.to_visit and len(self.visited_urls) < self.max_pages:
            if not self.to_visit:
                break
                
            url, depth = self.to_visit.popleft()
            
            if url in self.visited_urls or depth > max_depth:
                continue
                
            try:
                print(f"Crawling: {url}")
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                if 'text/html' in response.headers.get('content-type', ''):
                    # Extract content
                    title, content = self.extract_content(response.text, url)
                    
                    if content and len(content) > 100:  # Only index substantial content
                        # Add to search engine
                        search_engine.add_document(f"doc_{doc_id}", title, content, url)
                        doc_id += 1
                        
                        # Extract and add new links
                        if depth < max_depth:
                            new_links = self.extract_links(response.text, url)
                            for link in new_links:
                                if link not in self.visited_urls:
                                    self.to_visit.append((link, depth + 1))
                    
                    self.visited_urls.add(url)
                    
                time.sleep(self.delay)  # Be polite
                
            except Exception as e:
                print(f"Error crawling {url}: {e}")
                continue
        
        print(f"Crawling completed. Indexed {doc_id} pages.")
