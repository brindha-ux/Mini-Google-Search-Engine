from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import os
from typing import List, Optional

from search_engine import MiniGoogleSearch
from crawler import WebCrawler

app = FastAPI(title="Mini Google Search API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize search engine
search_engine = MiniGoogleSearch()

class SearchResponse(BaseModel):
    query: str
    results: List[dict]
    total_results: int
    search_time: float

class CrawlRequest(BaseModel):
    urls: List[str]
    max_pages: int = 50

@app.on_event("startup")
async def startup_event():
    """Load existing index on startup"""
    search_engine.load_index()

@app.get("/")
async def root():
    return {"message": "Mini Google Search API", "status": "running"}

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Number of results")
):
    """Search endpoint"""
    import time
    start_time = time.time()
    
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    results = search_engine.search(q, top_k=limit)
    search_time = time.time() - start_time
    
    return SearchResponse(
        query=q,
        results=results,
        total_results=len(results),
        search_time=search_time
    )

@app.post("/crawl")
async def start_crawl(crawl_request: CrawlRequest):
    """Start web crawling"""
    if not crawl_request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    
    crawler = WebCrawler(max_pages=crawl_request.max_pages)
    
    # Run crawling in background
    def crawl_background():
        crawler.crawl(crawl_request.urls, search_engine)
        search_engine.save_index()
    
    import threading
    thread = threading.Thread(target=crawl_background)
    thread.daemon = True
    thread.start()
    
    return {
        "message": f"Crawling started for {len(crawl_request.urls)} seed URLs",
        "max_pages": crawl_request.max_pages,
        "status": "processing"
    }

@app.get("/stats")
async def get_stats():
    """Get search engine statistics"""
    return {
        "total_documents": search_engine.total_docs,
        "index_size": len(search_engine.inverted_index),
        "status": "healthy"
    }

@app.get("/admin")
async def admin_page():
    """Simple admin interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mini Google Admin</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }
            input, textarea { width: 100%; padding: 8px; margin: 5px 0; }
            button { background: #4285f4; color: white; padding: 10px 20px; border: none; cursor: pointer; }
            .result { background: #f9f9f9; padding: 10px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Mini Google Search Engine</h1>
            
            <div class="section">
                <h2>Search</h2>
                <input type="text" id="searchQuery" placeholder="Enter your search query...">
                <button onclick="performSearch()">Search</button>
                <div id="searchResults"></div>
            </div>
            
            <div class="section">
                <h2>Crawl Websites</h2>
                <textarea id="crawlUrls" placeholder="Enter URLs to crawl (one per line)" rows="4">https://en.wikipedia.org/wiki/Artificial_intelligence
https://en.wikipedia.org/wiki/Machine_learning
https://en.wikipedia.org/wiki/Computer_science</textarea>
                <input type="number" id="maxPages" value="50" placeholder="Max pages">
                <button onclick="startCrawl()">Start Crawling</button>
                <div id="crawlStatus"></div>
            </div>
            
            <div class="section">
                <h2>Statistics</h2>
                <button onclick="getStats()">Refresh Stats</button>
                <div id="stats"></div>
            </div>
        </div>
        
        <script>
            async function performSearch() {
                const query = document.getElementById('searchQuery').value;
                const response = await fetch(`/search?q=${encodeURIComponent(query)}&limit=10`);
                const data = await response.json();
                
                let html = `<h3>Results (${data.total_results} found in ${data.search_time.toFixed(3)}s):</h3>`;
                data.results.forEach(result => {
                    html += `<div class="result">
                        <strong><a href="${result.url}" target="_blank">${result.title}</a></strong>
                        <div>${result.snippet}</div>
                        <small>Score: ${result.score.toFixed(4)} | URL: ${result.url}</small>
                    </div>`;
                });
                document.getElementById('searchResults').innerHTML = html;
            }
            
            async function startCrawl() {
                const urls = document.getElementById('crawlUrls').value.split('\\n').filter(url => url.trim());
                const maxPages = document.getElementById('maxPages').value;
                
                const response = await fetch('/crawl', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({urls: urls, max_pages: parseInt(maxPages)})
                });
                const data = await response.json();
                document.getElementById('crawlStatus').innerHTML = `<p>${data.message}</p>`;
            }
            
            async function getStats() {
                const response = await fetch('/stats');
                const data = await response.json();
                document.getElementById('stats').innerHTML = `
                    <p>Total Documents: ${data.total_documents}</p>
                    <p>Index Size: ${data.index_size} terms</p>
                    <p>Status: ${data.status}</p>
                `;
            }
            
            // Load stats on page load
            getStats();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
