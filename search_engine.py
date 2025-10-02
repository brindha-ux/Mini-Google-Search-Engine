import numpy as np
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
import re
import json
import os
from collections import defaultdict, Counter
import math
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle

# Download NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class MiniGoogleSearch:
    def __init__(self):
        self.index_path = "data/index/"
        self.documents = {}
        self.inverted_index = defaultdict(dict)
        self.doc_lengths = {}
        self.avg_doc_length = 0
        self.total_docs = 0
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=10000)
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        
        # Create directories
        os.makedirs(self.index_path, exist_ok=True)
        
    def preprocess_text(self, text):
        """Clean and preprocess text for indexing"""
        # Convert to lowercase
        text = text.lower()
        # Remove special characters and digits
        text = re.sub(r'[^a-zA-Z\s]', '', text)
        # Tokenize
        tokens = word_tokenize(text)
        # Remove stopwords and stem
        tokens = [self.stemmer.stem(token) for token in tokens 
                 if token not in self.stop_words and len(token) > 2]
        return tokens
    
    def add_document(self, doc_id, title, content, url):
        """Add a document to the search index"""
        full_text = f"{title} {content}"
        tokens = self.preprocess_text(full_text)
        
        # Store document info
        self.documents[doc_id] = {
            'title': title,
            'content': content[:200] + "...",  # Store snippet
            'url': url,
            'tokens': tokens
        }
        
        # Update inverted index
        token_counts = Counter(tokens)
        for token, count in token_counts.items():
            if doc_id not in self.inverted_index[token]:
                self.inverted_index[token][doc_id] = 0
            self.inverted_index[token][doc_id] += count
            
        self.total_docs += 1
        
    def build_tfidf_index(self):
        """Build TF-IDF matrix for all documents"""
        documents_text = []
        doc_ids = []
        
        for doc_id, doc in self.documents.items():
            documents_text.append(" ".join(doc['tokens']))
            doc_ids.append(doc_id)
            
        if documents_text:
            self.tfidf_matrix = self.vectorizer.fit_transform(documents_text)
            self.feature_names = self.vectorizer.get_feature_names_out()
            self.doc_ids = doc_ids
            
    def bm25_score(self, query, doc_id, k1=1.5, b=0.75):
        """Calculate BM25 relevance score"""
        if doc_id not in self.documents:
            return 0
            
        doc_tokens = self.documents[doc_id]['tokens']
        query_tokens = self.preprocess_text(query)
        
        score = 0
        doc_length = len(doc_tokens)
        
        for token in query_tokens:
            if token in self.inverted_index and doc_id in self.inverted_index[token]:
                # Term frequency in document
                tf = self.inverted_index[token][doc_id]
                # Document frequency
                df = len(self.inverted_index[token])
                # Inverse document frequency
                idf = math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1.0)
                
                # BM25 component
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_length / self.avg_doc_length))
                score += idf * (numerator / denominator)
                
        return score
    
    def search(self, query, top_k=10):
        """Search for documents matching the query"""
        if self.total_docs == 0:
            return []
            
        query_tokens = self.preprocess_text(query)
        
        # Calculate scores using multiple methods
        results = []
        
        for doc_id in self.documents:
            # BM25 score
            bm25_score = self.bm25_score(query, doc_id)
            
            # Simple term frequency score
            tf_score = 0
            for token in query_tokens:
                if token in self.inverted_index and doc_id in self.inverted_index[token]:
                    tf_score += self.inverted_index[token][doc_id]
            
            # Combine scores (you can adjust weights)
            combined_score = bm25_score * 0.7 + tf_score * 0.3
            
            if combined_score > 0:
                results.append({
                    'doc_id': doc_id,
                    'score': combined_score,
                    'title': self.documents[doc_id]['title'],
                    'snippet': self.documents[doc_id]['content'],
                    'url': self.documents[doc_id]['url']
                })
        
        # Sort by score and return top results
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def save_index(self):
        """Save search index to disk"""
        index_data = {
            'documents': self.documents,
            'inverted_index': dict(self.inverted_index),
            'total_docs': self.total_docs
        }
        
        with open(os.path.join(self.index_path, 'search_index.json'), 'w') as f:
            json.dump(index_data, f)
            
        # Save vectorizer
        with open(os.path.join(self.index_path, 'vectorizer.pkl'), 'wb') as f:
            pickle.dump(self.vectorizer, f)
    
    def load_index(self):
        """Load search index from disk"""
        try:
            with open(os.path.join(self.index_path, 'search_index.json'), 'r') as f:
                index_data = json.load(f)
                
            self.documents = index_data['documents']
            self.inverted_index = defaultdict(dict, index_data['inverted_index'])
            self.total_docs = index_data['total_docs']
            
            # Load vectorizer
            with open(os.path.join(self.index_path, 'vectorizer.pkl'), 'rb') as f:
                self.vectorizer = pickle.load(f)
                
            print(f"Loaded index with {self.total_docs} documents")
            return True
        except FileNotFoundError:
            print("No existing index found")
            return False
